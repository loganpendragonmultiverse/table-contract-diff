from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import compare_profiles, profile_csv


def _markdown(report: dict[str, object]) -> str:
    added = report["addedColumns"]
    removed = report["removedColumns"]
    assert isinstance(added, list) and all(isinstance(item, str) for item in added)
    assert isinstance(removed, list) and all(isinstance(item, str) for item in removed)
    lines = [
        "# Table Contract Diff report",
        "",
        f"- Breaking change: **{report['breakingChange']}**",
        f"- Added columns: {', '.join(added) or 'none'}",
        f"- Removed columns: {', '.join(removed) or 'none'}",
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
        lines.append(f"| {item['code']} | {item['column']} | {item['before']} | {item['after']} |")
    candidates = report["renameCandidates"]
    assert isinstance(candidates, list)
    if candidates:
        lines.extend(["", "## Rename candidates", ""])
        for item in candidates:
            assert isinstance(item, dict)
            lines.append(f"- `{item['from']}` → `{item['to']}` ({item['similarity']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two CSV data contracts locally.")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-schema", type=Path)
    parser.add_argument("--current-schema", type=Path)
    parser.add_argument("--fail-breaking", action="store_true")
    args = parser.parse_args(argv)
    if not args.baseline.is_file() or not args.current.is_file():
        parser.error("baseline and current CSV files must exist")
    baseline = profile_csv(args.baseline)
    current = profile_csv(args.current)
    report = compare_profiles(baseline, current)
    rendered = json.dumps(report, indent=2) if args.format == "json" else _markdown(report)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.baseline_schema:
        args.baseline_schema.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    if args.current_schema:
        args.current_schema.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return int(args.fail_breaking and bool(report["breakingChange"]))
