from pathlib import Path

import pytest

from table_contract_diff.cli import main
from table_contract_diff.core import _cell_type, _merge_types, compare_profiles, profile_csv


def test_profiles_types_and_dialect(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text(
        "id;active;amount;date;note\n1;yes;1.5;2026-08-10;hello\n2;no;;2026-08-11;\n",
        encoding="utf-8",
    )
    profile = profile_csv(path)
    assert profile["delimiter"] == ";"
    columns = {item["name"]: item for item in profile["columns"]}  # type: ignore[index]
    assert columns["id"]["inferred_type"] == "integer"
    assert columns["active"]["inferred_type"] == "boolean"
    assert columns["amount"]["nullable"] is True


def test_compares_breaking_changes_and_rename(tmp_path: Path) -> None:
    before = tmp_path / "before.csv"
    after = tmp_path / "after.csv"
    before.write_text("customer_id,amount\n1,5\n", encoding="utf-8")
    after.write_text("customer_identifier,amount,extra\n1,text,x\n", encoding="utf-8")
    report = compare_profiles(profile_csv(before), profile_csv(after))
    assert report["breakingChange"] is True
    assert report["renameCandidates"]
    assert any(item["code"] == "type-changed" for item in report["changes"])  # type: ignore[index]


def test_cli_writes_schemas_and_fails_breaking(tmp_path: Path) -> None:
    before, after = tmp_path / "a.csv", tmp_path / "b.csv"
    before.write_text("a,b\n1,2\n", encoding="utf-8")
    after.write_text("a\n1\n", encoding="utf-8")
    report, left, right = tmp_path / "report.json", tmp_path / "left.json", tmp_path / "right.json"
    assert (
        main(
            [
                str(before),
                str(after),
                "--format",
                "json",
                "--output",
                str(report),
                "--baseline-schema",
                str(left),
                "--current-schema",
                str(right),
                "--fail-breaking",
            ]
        )
        == 1
    )
    assert report.is_file() and left.is_file() and right.is_file()


def test_rejects_empty_duplicate_and_bad_rows(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        profile_csv(empty)
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text("a,a\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        profile_csv(duplicate)
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1\n", encoding="utf-8")
    assert profile_csv(bad)["invalidRowCount"] == 1


def test_cell_type_and_merge_rules() -> None:
    assert _cell_type("") == "null"
    assert _cell_type("3") == "integer"
    assert _cell_type("3.2") == "decimal"
    assert _cell_type("2026-08-10T12:00:00") == "datetime"
    assert _cell_type("hello") == "text"
    assert _merge_types({"integer", "decimal", "null"}) == "decimal"
    assert _merge_types({"integer", "text"}) == "mixed"


def test_cli_markdown_and_validation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    before, after = tmp_path / "before.csv", tmp_path / "after.csv"
    before.write_text("old_name,value\n1,2\n", encoding="utf-8")
    after.write_text("old_names,value\n1,2\n", encoding="utf-8")
    assert main([str(before), str(after)]) == 0
    assert "Rename candidates" in capsys.readouterr().out
    blank_header = tmp_path / "blank.csv"
    blank_header.write_text(",b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty"):
        profile_csv(blank_header)
    with pytest.raises(SystemExit):
        main([str(tmp_path / "missing.csv"), str(after)])
