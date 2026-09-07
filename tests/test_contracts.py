import json
from pathlib import Path

import pytest

from table_contract_diff.cli import main
from table_contract_diff.contracts import check_contract, review_changes, validate_profile
from table_contract_diff.core import compare_profiles, profile_csv


def test_locale_nulls_expected_contract_and_private_html(tmp_path: Path) -> None:
    before, after = tmp_path / "before.csv", tmp_path / "after.csv"
    before.write_text(
        'amount;date;note\n"1.234,50";31/12/2025;PRIVATE-CELL-CANARY\n', encoding="utf-8"
    )
    after.write_text("amount;date;note\nNULL;01/01/2026;PRIVATE-CELL-CANARY\n", encoding="utf-8")
    settings = {
        "delimiter": ";",
        "null_values": ["", "NULL"],
        "decimal_separator": ",",
        "thousands_separator": ".",
        "date_format": "%d/%m/%Y",
    }
    profile = profile_csv(before, settings)
    assert [c["inferred_type"] for c in profile["columns"]] == ["decimal", "date", "text"]
    expected = {
        "columns": {
            "amount": {"type": "decimal", "nullable": False},
            "date": {"type": "date", "nullable": False},
            "optional": {"type": "text", "nullable": True, "required": False},
        },
        "allow_extra": True,
    }
    assert check_contract(profile, expected) == []
    violations = check_contract(profile_csv(after, settings), expected)
    assert {v["code"] for v in violations} == {"expected-type", "unexpected-null"}
    profiles, schema = tmp_path / "profiles.json", tmp_path / "schema.json"
    profiles.write_text(json.dumps({"eu": settings}), encoding="utf-8")
    schema.write_text(json.dumps(expected), encoding="utf-8")
    for fmt in ("html", "json", "markdown"):
        output = tmp_path / (fmt + ".out")
        assert (
            main(
                [
                    str(before),
                    str(after),
                    "--profiles",
                    str(profiles),
                    "--profile",
                    "eu",
                    "--expected-schema",
                    str(schema),
                    "--format",
                    fmt,
                    "--output",
                    str(output),
                    "--fail-breaking",
                ]
            )
            == 1
        )
        assert "PRIVATE-CELL-CANARY" not in output.read_text(encoding="utf-8")


def test_exact_approval_preserves_observed_breaking_change(tmp_path: Path) -> None:
    before, after = tmp_path / "before.csv", tmp_path / "after.csv"
    before.write_text("id,old\n1,x\n", encoding="utf-8")
    after.write_text("id\n1\n", encoding="utf-8")
    report = compare_profiles(profile_csv(before), profile_csv(after))
    rule = {
        "code": "column-removed",
        "column": "old",
        "before": True,
        "after": False,
        "explanation": "Owner approved retiring the old field",
    }
    assert report["breakingChange"]
    assert not review_changes(report, [rule])["unapprovedBreakingChange"]
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps([rule]), encoding="utf-8")
    assert main([str(before), str(after), "--approved-rules", str(rules), "--fail-breaking"]) == 0
    assert main([str(before), str(after), "--output", str(before)]) == 2


@pytest.mark.parametrize(
    "profile",
    [
        [],
        {"delimiter": "xx"},
        {"null_values": [1]},
        {"date_format": 1},
        {"unknown": True},
        {"decimal_separator": ",", "thousands_separator": ","},
    ],
)
def test_invalid_profiles(profile: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        validate_profile(profile)


def test_contract_shape_missing_extra_and_invalid_rows(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id,other\n1,x\nwrong\n", encoding="utf-8")
    profile = profile_csv(path, {"delimiter": ","})
    expected = {"columns": {"missing": {"type": "integer", "nullable": False}}}
    assert {v["code"] for v in check_contract(profile, expected)} == {
        "required-column-missing",
        "unexpected-column",
        "invalid-row-width",
    }
    for value in (
        [],
        {"columns": [], "allow_extra": False},
        {"columns": {}, "allow_extra": "yes"},
        {"columns": {"id": {}}},
    ):
        with pytest.raises((TypeError, ValueError)):
            check_contract(profile, value)
    for rules in ({}, [{}]):
        with pytest.raises((TypeError, ValueError)):
            review_changes({"changes": [], "removedColumns": []}, rules)
