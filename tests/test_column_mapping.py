import copy
import json
from pathlib import Path

import pytest

from table_contract_diff.cli import main
from table_contract_diff.contracts import apply_column_mapping
from table_contract_diff.core import profile_csv


def files(tmp_path: Path, current_value: str = "1") -> tuple[Path, Path, Path]:
    before, after, mapping = tmp_path / "old.csv", tmp_path / "new.csv", tmp_path / "mapping.json"
    before.write_text("old_id,note\n1,PRIVATE-CELL-CANARY\n", encoding="utf-8")
    after.write_text(f"new_id,note\n{current_value},PRIVATE-CELL-CANARY\n", encoding="utf-8")
    mapping.write_text(
        json.dumps([{"from": "old_id", "to": "new_id", "explanation": "Reviewed header change"}]),
        encoding="utf-8",
    )
    return before, after, mapping


@pytest.mark.parametrize("fmt", ["json", "markdown", "html"])
def test_header_mapping_is_reviewed_and_value_free(tmp_path: Path, fmt: str) -> None:
    before, after, mapping = files(tmp_path)
    originals = {p: p.read_bytes() for p in (before, after, mapping)}
    out = tmp_path / (fmt + ".out")
    assert (
        main(
            [
                str(before),
                str(after),
                "--column-mapping",
                str(mapping),
                "--format",
                fmt,
                "--output",
                str(out),
                "--fail-breaking",
            ]
        )
        == 0
    )
    text = out.read_text(encoding="utf-8")
    assert "PRIVATE-CELL-CANARY" not in text
    assert "old_id" in text and "new_id" in text and "Reviewed header change" in text
    if fmt == "json":
        report = json.loads(text)
        assert report["breakingChange"] is True
        assert report["removedColumns"] == ["old_id"]
        assert report["addedColumns"] == ["new_id"]
        assert report["mappingReview"]["comparison"]["changes"] == []
        assert report["effectiveBreakingChange"] is False
    assert all(p.read_bytes() == content for p, content in originals.items())


def test_mapping_does_not_approve_semantic_changes_or_contracts(tmp_path: Path) -> None:
    before, after, mapping = files(tmp_path, "text")
    args = [str(before), str(after), "--column-mapping", str(mapping), "--fail-breaking"]
    assert main(args) == 1
    rule = {
        "code": "type-changed",
        "column": "new_id",
        "before": "integer",
        "after": "text",
        "explanation": "Reviewed type change",
    }
    approvals = tmp_path / "rules.json"
    approvals.write_text(json.dumps([rule]), encoding="utf-8")
    assert main(args + ["--approved-rules", str(approvals)]) == 0
    schema = tmp_path / "expected.json"
    schema.write_text(
        json.dumps(
            {"columns": {"new_id": {"type": "integer", "nullable": False}}, "allow_extra": True}
        ),
        encoding="utf-8",
    )
    assert main(args + ["--approved-rules", str(approvals), "--expected-schema", str(schema)]) == 1
    after.write_text("new_id,note\n,PRIVATE-CELL-CANARY\n", encoding="utf-8")
    output = tmp_path / "null.json"
    assert main(args + ["--format", "json", "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert {c["code"] for c in report["mappingReview"]["comparison"]["changes"]} == {
        "type-changed",
        "nullability-changed",
    }
    assert all(c["column"] == "new_id" for c in report["approvalReview"]["changes"])


@pytest.mark.parametrize(
    "mapping",
    [
        {},
        [None],
        [{}],
        [{"from": "old_id", "to": "new_id"}],
        [{"from": "old_id", "to": "new_id", "explanation": " "}],
        [{"from": "old_id", "to": "new_id", "explanation": 3}],
        [{"from": "old_id", "to": "new_id", "explanation": "review", "extra": True}],
        [{"from": "missing", "to": "new_id", "explanation": "review"}],
        [{"from": "note", "to": "new_id", "explanation": "review"}],
        [{"from": "old_id", "to": "note", "explanation": "review"}],
        [{"from": "old_id", "to": "old_id", "explanation": "review"}],
        [
            {"from": "old_id", "to": "new_id", "explanation": "a"},
            {"from": "old_id", "to": "other", "explanation": "b"},
        ],
        [
            {"from": "old_id", "to": "new_id", "explanation": "a"},
            {"from": "other_old", "to": "new_id", "explanation": "b"},
        ],
        [
            {"from": "old_id", "to": "new_id", "explanation": "a"},
            {"from": "new_id", "to": "old_id", "explanation": "cycle"},
        ],
    ],
)
def test_invalid_mappings_fail_closed(tmp_path: Path, mapping: object) -> None:
    before, after, _ = files(tmp_path)
    with pytest.raises((ValueError, TypeError)):
        apply_column_mapping(profile_csv(before), profile_csv(after), mapping)


def test_profiles_unchanged_and_mapping_order_deterministic(tmp_path: Path) -> None:
    before, after, _ = files(tmp_path)
    before.write_text("old_id,old_note\n1,x\n", encoding="utf-8")
    after.write_text("new_note,new_id\nx,1\n", encoding="utf-8")
    left, right = profile_csv(before), profile_csv(after)
    original = copy.deepcopy((left, right))
    mappings = [
        {"from": "old_note", "to": "new_note", "explanation": "review note"},
        {"from": "old_id", "to": "new_id", "explanation": "review id"},
    ]
    a = apply_column_mapping(left, right, mappings)
    assert a == apply_column_mapping(left, right, list(reversed(mappings)))
    assert (left, right) == original
    assert [c["name"] for c in a[0]["columns"]] == ["new_id", "new_note"]
    assert apply_column_mapping(left, right, [])[0] == left


def test_cli_rejects_duplicate_keys_and_large_mapping_without_output(tmp_path: Path) -> None:
    before, after, mapping = files(tmp_path)
    out = tmp_path / "out.json"
    args = [str(before), str(after), "--column-mapping", str(mapping), "--output", str(out)]
    mapping.write_text(
        '[{"from":"old_id","from":"note","to":"new_id","explanation":"review"}]', encoding="utf-8"
    )
    assert main(args) == 2
    assert not out.exists()
    mapping.write_bytes(b" " * 1_000_001)
    assert main(args) == 2
    assert not out.exists()
    mapping.write_text("not JSON", encoding="utf-8")
    assert main(args) == 2
    mapping.write_text("[]", encoding="utf-8")
    assert main(args + ["--fail-breaking"]) == 1


def test_html_escapes_mapping_headers_and_explanations(tmp_path: Path) -> None:
    before, after, mapping = files(tmp_path)
    before.write_text("<script>,note\n1,x\n", encoding="utf-8")
    after.write_text("<img>,note\n1,x\n", encoding="utf-8")
    mapping.write_text(
        json.dumps(
            [{"from": "<script>", "to": "<img>", "explanation": "<script>alert(1)</script>"}]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "safe.html"
    assert (
        main(
            [
                str(before),
                str(after),
                "--column-mapping",
                str(mapping),
                "--format",
                "html",
                "--output",
                str(out),
            ]
        )
        == 0
    )
    html = out.read_text(encoding="utf-8")
    assert "<script>" not in html and "<img>" not in html
    assert "&lt;script&gt;" in html and "&lt;img&gt;" in html
