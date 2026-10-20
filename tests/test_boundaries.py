import csv
import hashlib
import json
from pathlib import Path

import pytest

from table_contract_diff import _io
from table_contract_diff.cli import main
from table_contract_diff.contracts import review_changes, validate_profile
from table_contract_diff.core import _cell_type, profile_csv


def sources(tmp_path):
    before, after = tmp_path / "before.csv", tmp_path / "after.csv"
    before.write_text("id,value\n1,10\n")
    after.write_text("id,value\n1,10.5\n")
    return before, after


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-10-20 00:00:00", "datetime"),
        ("2026-10-20T00:00:00", "datetime"),
        ("2026-10-20", "date"),
        ("2026-W43-2", "date"),
        ("2026-W54-2", "text"),
        ("2026-W43-0", "text"),
    ],
)
def test_midnight_and_date_inference(value, expected):
    assert _cell_type(value) == expected


def test_approved_rules_do_not_conflate_numbers_and_booleans():
    report = {"changes": [], "removedColumns": ["old"]}
    rule = {
        "code": "column-removed",
        "column": "old",
        "before": 1,
        "after": 0,
        "explanation": "numeric values are not boolean consent",
    }
    assert review_changes(report, [rule])["unapprovedBreakingChange"] is True
    assert (
        review_changes(report, [{**rule, "before": True, "after": False}])[
            "unapprovedBreakingChange"
        ]
        is False
    )


def test_aggregate_profiles_preserve_counts_and_original_hash(tmp_path):
    path = tmp_path / "data.csv"
    raw = b"\xef\xbb\xbfid,value\n1,10\n2,\ninvalid\n3,2.5\n"
    path.write_bytes(raw)
    profile = profile_csv(path, {"delimiter": ","})
    assert profile["sourceSha256"] == hashlib.sha256(raw).hexdigest()
    assert profile["rowCount"] == 4 and profile["invalidRowCount"] == 1
    value = profile["columns"][1]
    assert value["inferred_type"] == "decimal" and value["null_count"] == 1
    assert value["non_null_count"] == 2 and value["max_length"] == 3


def test_malformed_and_oversized_fields_are_value_free_errors(tmp_path, capsys):
    before, after = sources(tmp_path)
    after.write_text('id,value\n1,"PRIVATE-CANARY')
    assert main([str(before), str(after)]) == 2
    assert "PRIVATE-CANARY" not in capsys.readouterr().err
    old = csv.field_size_limit()
    try:
        csv.field_size_limit(32)
        after.write_text("id,value\n1,PRIVATE-CANARY" + "x" * 64 + "\n")
        assert main([str(before), str(after)]) == 2
        assert "PRIVATE-CANARY" not in capsys.readouterr().err
    finally:
        csv.field_size_limit(old)


@pytest.mark.parametrize(
    "option", ["--profiles", "--approved-rules", "--expected-schema", "--column-mapping"]
)
def test_auxiliary_json_is_unambiguous(tmp_path, option):
    before, after = sources(tmp_path)
    aux = tmp_path / "aux.json"
    output = tmp_path / "out.json"
    for text in ['{"x":1,"x":2}', '{"x":NaN}']:
        aux.write_text(text)
        assert main([str(before), str(after), option, str(aux), "--output", str(output)]) == 2
        assert not output.exists()


@pytest.mark.parametrize(
    "profile", [{"delimiter": None}, {"delimiter": "\n"}, {"decimal_separator": "\0"}]
)
def test_unusable_delimiters_are_refused(profile):
    with pytest.raises(ValueError):
        validate_profile(profile)


def test_input_size_and_encoding_boundaries(tmp_path, monkeypatch):
    before, after = sources(tmp_path)
    monkeypatch.setattr(_io, "MAX_INPUT_BYTES", 64)
    after.write_bytes(b"x" * 65)
    assert main([str(before), str(after)]) == 2
    after.write_bytes(b"\xff")
    assert main([str(before), str(after)]) == 2


def test_report_preflight_preserves_all_inputs_and_existing_outputs(tmp_path):
    before, after = sources(tmp_path)
    output = tmp_path / "out.json"
    schema = tmp_path / "schema.json"
    schema.write_text("keep")
    args = [str(before), str(after), "--output", str(output)]
    assert main(args + ["--current-schema", str(schema)]) == 2
    assert not output.exists() and schema.read_text() == "keep"
    assert main(args + ["--current-schema", str(output)]) == 2
    assert not output.exists()
    assert main([str(before), str(after), "--output", str(tmp_path / "absent" / "out")]) == 2


def test_competing_report_and_permission_failures_are_actionable(tmp_path, monkeypatch):
    before, after = sources(tmp_path)
    output = tmp_path / "out.json"
    original = Path.open

    def race(candidate, mode="r", *args, **kwargs):
        if candidate == output and mode == "x":
            with original(candidate, "w", encoding="utf-8") as handle:
                handle.write("other writer")
        return original(candidate, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", race)
    assert main([str(before), str(after), "--output", str(output)]) == 2
    assert output.read_text() == "other writer"

    def denied(candidate, mode="r", *args, **kwargs):
        if mode == "x":
            raise PermissionError("synthetic write failure")
        return original(candidate, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    denied_output = tmp_path / "denied.json"
    assert main([str(before), str(after), "--output", str(denied_output)]) == 2
    assert not denied_output.exists()


def test_symlink_inputs_and_dangling_outputs_are_refused(tmp_path):
    before, after = sources(tmp_path)
    link = tmp_path / "link.csv"
    output = tmp_path / "out.json"
    absent = tmp_path / "absent.json"
    try:
        link.symlink_to(before)
        output.symlink_to(absent)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    assert main([str(link), str(after)]) == 2
    assert main([str(before), str(after), "--output", str(output)]) == 2
    assert not absent.exists() and output.is_symlink()
    with pytest.raises(ValueError):
        _io.write_new(output, "preserve")


def test_literal_headers_are_escaped_without_cell_values(tmp_path):
    before, after = sources(tmp_path)
    with before.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["<script>|header\n```", "note"])
        writer.writerow([1, "PRIVATE-CANARY"])
    with after.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["<script>|header\n```", "note"])
        writer.writerow(["text", "PRIVATE-CANARY"])
    for fmt in ["markdown", "html", "json"]:
        output = tmp_path / (fmt + ".out")
        assert main([str(before), str(after), "--format", fmt, "--output", str(output)]) == 0
        text = output.read_text()
        assert "PRIVATE-CANARY" not in text
        if fmt == "markdown":
            assert "&lt;script&gt;&#124;header" in text
            assert "````json" in text
        if fmt == "html":
            assert "<script>" not in text and "&lt;script&gt;" in text


def test_shipped_examples_have_expected_breaking_exit():
    examples = Path(__file__).parents[1] / "examples"
    assert (
        main(
            [
                str(examples / "before.csv"),
                str(examples / "after.csv"),
                "--format",
                "json",
                "--fail-breaking",
            ]
        )
        == 1
    )


@pytest.mark.parametrize("depth", [129, 1100], ids=["bounded-depth", "parser-depth"])
@pytest.mark.parametrize(
    "option", ["--profiles", "--approved-rules", "--expected-schema", "--column-mapping"]
)
def test_nested_json_returns_actionable_error(tmp_path, capsys, depth, option):
    before, after = sources(tmp_path)
    path = tmp_path / "nested.json"
    path.write_text("[" * depth + "0" + "]" * depth)
    assert main([str(before), str(after), option, str(path)]) == 2
    assert "nesting" in capsys.readouterr().err


def test_markdown_headers_render_links_emphasis_and_code_literally(tmp_path):
    before, after = sources(tmp_path)
    header = r"[review](https://example.test/) **VERIFIED** `code` \path"
    for path, value in [(before, "1"), (after, "text")]:
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([header])
            writer.writerow([value])
    output = tmp_path / "report.md"
    assert main([str(before), str(after), "--output", str(output)]) == 0
    assert (
        r"\[review\]\(https://example.test/\) \*\*VERIFIED\*\* \`code\` \\path"
        in output.read_text()
    )


@pytest.mark.parametrize("delimiter", [";", "\t", ","], ids=["semicolon", "tab", "unchanged"])
def test_delimiter_comparison_is_visible_and_informational(tmp_path, delimiter):
    before, after = sources(tmp_path)
    before.write_text("id,value\n1,10\n")
    after.write_text("id" + delimiter + "value\n1" + delimiter + "10\n")
    for fmt in ["json", "markdown", "html"]:
        output = tmp_path / (fmt + ".out")
        assert (
            main(
                [
                    str(before),
                    str(after),
                    "--format",
                    fmt,
                    "--output",
                    str(output),
                    "--fail-breaking",
                ]
            )
            == 0
        )
        text = output.read_text()
        if fmt == "json":
            report = json.loads(text)
            assert report["delimiterComparison"] == {
                "before": ",",
                "after": delimiter,
                "changed": delimiter != ",",
            }
            assert report["breakingChange"] is False
            assert report["effectiveBreakingChange"] is False
            assert report["approvalReview"]["changes"] == []
        else:
            assert "Parsing delimiter:" in text and "informational" in text
            assert str(delimiter != ",") in text
            if delimiter == "\t":
                assert r"\t" in text


def test_finite_json_fractions_remain_supported(tmp_path):
    path = tmp_path / "finite.json"
    path.write_text('{"fraction":1.25,"tiny":1e-10}')
    assert _io.load_json(path) == {"fraction": 1.25, "tiny": 1e-10}


@pytest.mark.parametrize("number", ["1e400", "-1e400"])
@pytest.mark.parametrize(
    "option", ["--profiles", "--approved-rules", "--expected-schema", "--column-mapping"]
)
def test_json_numeric_overflow_is_rejected_for_every_input(tmp_path, capsys, number, option):
    before, after = sources(tmp_path)
    bad = tmp_path / "overflow.json"
    bad.write_text('{"number":' + number + "}")
    assert main([str(before), str(after), option, str(bad)]) == 2
    assert "numbers must be finite" in capsys.readouterr().err
