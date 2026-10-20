from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from ._io import load_json, preflight, write_new
from .contracts import apply_column_mapping, check_contract, render_html, review_changes
from .core import compare_profiles, profile_csv


def _json_block(value: object) -> str:
    text = json.dumps(value, indent=2)
    fence = "`" * max(
        3, 1 + max((len(match.group()) for match in re.finditer(r"`+", text)), default=0)
    )
    return fence + "json\n" + text + "\n" + fence


def _markdown(report: dict[str, object]) -> str:
    def cell(value: object) -> str:
        literal = re.sub(r"([\\`*_{}\[\]()!~])", r"\\\1", html.escape(str(value)))
        return literal.replace("|", "&#124;").replace("\r", " ").replace("\n", " ")

    added = report["addedColumns"]
    removed = report["removedColumns"]
    assert isinstance(added, list) and all(isinstance(item, str) for item in added)
    assert isinstance(removed, list) and all(isinstance(item, str) for item in removed)
    delimiter = report.get("delimiterComparison", {})
    assert isinstance(delimiter, dict)
    lines = [
        "# Table Contract Diff report",
        "",
        f"- Breaking change: **{report['breakingChange']}**",
        (
            f"- Parsing delimiter: {cell(json.dumps(delimiter.get('before')))} → "
            f"{cell(json.dumps(delimiter.get('after')))}; changed: {delimiter.get('changed')} (informational)"
        ),
        f"- Added columns: {cell(', '.join(added) or 'none')}",
        f"- Removed columns: {cell(', '.join(removed) or 'none')}",
        f"- Invalid-row delta: {report['invalidRowDelta']}",
        "",
        "| Change | Column | Before | After |",
        "|---|---|---|---|",
    ]
    changes = report["changes"]
    assert isinstance(changes, list)
    if not changes:
        lines.append("| none | - | - | - |")
    for item in changes:
        assert isinstance(item, dict)
        lines.append(
            f"| {item['code']} | {cell(item['column'])} | {cell(item['before'])} | {cell(item['after'])} |"
        )
    candidates = report["renameCandidates"]
    assert isinstance(candidates, list)
    if candidates:
        lines.extend(["", "## Rename candidates", ""])
        for item in candidates:
            assert isinstance(item, dict)
            lines.append(f"- {cell(item['from'])} → {cell(item['to'])} ({item['similarity']})")
    if "mappingReview" in report:
        lines.extend(
            [
                "",
                "## Explicit column mapping",
                "",
                "Original structural breakingChange is retained; mapped type/nullability changes and expected-schema violations still require review.",
                "",
                _json_block(report["mappingReview"]),
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two CSV data contracts locally.")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--format", choices=("json", "markdown", "html"), default="markdown")
    parser.add_argument("--expected-schema", type=Path)
    parser.add_argument("--approved-rules", type=Path)
    parser.add_argument(
        "--column-mapping", type=Path, help="reviewed removed-to-added mapping JSON"
    )
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--profile", default="default")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-schema", type=Path)
    parser.add_argument("--current-schema", type=Path)
    parser.add_argument("--fail-breaking", action="store_true")
    args = parser.parse_args(argv)
    if not args.baseline.is_file() or not args.current.is_file():
        parser.error("baseline and current CSV files must exist")
    try:
        targets = [p for p in (args.output, args.baseline_schema, args.current_schema) if p]
        preflight(targets)
        profiles = load_json(args.profiles) if args.profiles else {"default": {}}
        if not isinstance(profiles, dict) or args.profile not in profiles:
            raise ValueError("selected parsing profile is missing")
        baseline = profile_csv(args.baseline, profiles[args.profile])
        current = profile_csv(args.current, profiles[args.profile])
        report = compare_profiles(baseline, current)
        comparison = report
        if args.column_mapping:
            aligned, mappings = apply_column_mapping(
                baseline,
                current,
                load_json(args.column_mapping, limit=1_000_000),
            )
            comparison = compare_profiles(aligned, current)
            report["mappingReview"] = {"mappings": mappings, "comparison": comparison}
        report["approvalReview"] = review_changes(
            comparison,
            load_json(args.approved_rules) if args.approved_rules else [],
        )
        report["contractViolations"] = (
            check_contract(current, load_json(args.expected_schema)) if args.expected_schema else []
        )
        report["effectiveBreakingChange"] = report["approvalReview"][
            "unapprovedBreakingChange"
        ] or bool(report["contractViolations"])
        rendered = (
            render_html(report, baseline, current)
            if args.format == "html"
            else json.dumps(report, indent=2)
            if args.format == "json"
            else _markdown(report)
            + "\n\n## Explicit contract review\n\n"
            + _json_block(
                {"approvals": report["approvalReview"], "violations": report["contractViolations"]}
            )
        )
        reports = []
        if args.output:
            reports.append((args.output, rendered + "\n"))
        if args.baseline_schema:
            reports.append((args.baseline_schema, json.dumps(baseline, indent=2) + "\n"))
        if args.current_schema:
            reports.append((args.current_schema, json.dumps(current, indent=2) + "\n"))
        for path, content in reports:
            write_new(path, content)
        if not args.output:
            print(rendered)
    except (OSError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return int(args.fail_breaking and bool(report["effectiveBreakingChange"]))
