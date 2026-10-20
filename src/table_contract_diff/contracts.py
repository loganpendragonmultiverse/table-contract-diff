"""Explicit operator contracts, parsing profiles and value-free HTML review."""

from __future__ import annotations

import html
import json
from typing import Any

TYPES = {"text", "integer", "decimal", "boolean", "date", "datetime", "mixed", "unknown"}


def apply_column_mapping(
    before: dict[str, Any], after: dict[str, Any], mappings: Any
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Align only explicit removed-to-added columns; never rewrite the source profile."""
    if not isinstance(mappings, list):
        raise TypeError("column mapping must be an array")
    old_names = {c["name"] for c in before["columns"]}
    new_names = {c["name"] for c in after["columns"]}
    sources: set[str] = set()
    targets: set[str] = set()
    validated: list[dict[str, str]] = []
    for item in mappings:
        if (
            not isinstance(item, dict)
            or set(item) != {"from", "to", "explanation"}
            or any(not isinstance(item[k], str) or not item[k].strip() for k in item)
        ):
            raise ValueError("each column mapping needs exact from/to/explanation text fields")
        source, target = item["from"], item["to"]
        if source in sources or target in targets:
            raise ValueError("column mapping must be one-to-one without duplicate endpoints")
        if source not in old_names - new_names or target not in new_names - old_names:
            raise ValueError(
                "column mapping must pair an observed removed column with an added column"
            )
        sources.add(source)
        targets.add(target)
        validated.append(dict(item))
    validated.sort(key=lambda item: (item["from"], item["to"]))
    names = {item["from"]: item["to"] for item in validated}
    aligned = {
        **before,
        "columns": [{**c, "name": names.get(c["name"], c["name"])} for c in before["columns"]],
    }
    return aligned, validated


def validate_profile(profile: Any) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise TypeError("profile must be an object")
    if set(profile) - {
        "delimiter",
        "null_values",
        "decimal_separator",
        "thousands_separator",
        "date_format",
    }:
        raise ValueError("unknown parsing profile key")
    for key in ("delimiter", "decimal_separator", "thousands_separator"):
        value = profile.get(key)
        if key in profile and (not isinstance(value, str) or len(value) != 1 or value in "\r\n\0"):
            raise ValueError(f"{key} must be one character")
    nulls = profile.get("null_values", [""])
    if not isinstance(nulls, list) or any(not isinstance(v, str) for v in nulls):
        raise TypeError("null_values must be an array of text")
    if "date_format" in profile and not isinstance(profile["date_format"], str):
        raise TypeError("date_format must be text")
    if profile.get("thousands_separator") == profile.get("decimal_separator", "."):
        raise ValueError("decimal and thousands separators must differ")
    return dict(profile)


def check_contract(profile: dict[str, Any], expected: Any) -> list[dict[str, Any]]:
    if not isinstance(expected, dict) or not isinstance(expected.get("columns"), dict):
        raise TypeError("expected schema must contain a columns object")
    if not isinstance(expected.get("allow_extra", False), bool):
        raise TypeError("allow_extra must be boolean")
    observed = {item["name"]: item for item in profile["columns"]}
    violations = []
    for name, spec in expected["columns"].items():
        if (
            not isinstance(spec, dict)
            or spec.get("type") not in TYPES
            or not isinstance(spec.get("nullable"), bool)
            or not isinstance(spec.get("required", True), bool)
        ):
            raise ValueError(
                f"Expected column {name} needs type, nullable and optional required boolean"
            )
        if name not in observed:
            if spec.get("required", True):
                violations.append({"column": name, "code": "required-column-missing"})
            continue
        actual = observed[name]
        compatible = (
            actual["inferred_type"] == spec["type"]
            or spec["type"] == "decimal"
            and actual["inferred_type"] == "integer"
        )
        if not compatible:
            violations.append(
                {
                    "column": name,
                    "code": "expected-type",
                    "expected": spec["type"],
                    "observed": actual["inferred_type"],
                }
            )
        if not spec["nullable"] and actual["null_count"]:
            violations.append(
                {"column": name, "code": "unexpected-null", "count": actual["null_count"]}
            )
    if not expected.get("allow_extra", False):
        violations.extend(
            {"column": name, "code": "unexpected-column"}
            for name in sorted(observed.keys() - expected["columns"].keys())
        )
    if profile["invalidRowCount"]:
        violations.append({"code": "invalid-row-width", "count": profile["invalidRowCount"]})
    return violations


def review_changes(report: dict[str, Any], rules: Any) -> dict[str, Any]:
    if not isinstance(rules, list):
        raise TypeError("approved rules must be an array")
    candidates = [
        *report["changes"],
        *[
            {"code": "column-removed", "column": name, "before": True, "after": False}
            for name in report["removedColumns"]
        ],
    ]
    for rule in rules:
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("explanation"), str)
            or not rule["explanation"].strip()
            or any(k not in rule for k in ("code", "column", "before", "after"))
        ):
            raise ValueError(
                "Approved rules require exact code/column/before/after plus an explanation"
            )
    reviewed = []
    for change in candidates:
        matches = [
            r
            for r in rules
            if all(
                type(r[k]) is type(change[k]) and r[k] == change[k]
                for k in ("code", "column", "before", "after")
            )
        ]
        reviewed.append(
            {
                **change,
                "approved": bool(matches),
                "explanations": [r["explanation"] for r in matches],
            }
        )
    return {
        "changes": reviewed,
        "unapprovedBreakingChange": any(
            not c["approved"]
            and c["code"] in ("type-changed", "nullability-changed", "column-removed")
            for c in reviewed
        ),
        "note": "Approvals apply only to these observed changes; expected-schema violations remain separate",
    }


def render_html(report: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> str:
    old = {c["name"]: c for c in before["columns"]}
    new = {c["name"]: c for c in after["columns"]}
    parts = [
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Table contract review</title>',
        "<style>body{font:17px system-ui;max-width:1100px;margin:auto;padding:22px;background:#f5f1e8;color:#203442}article{background:white;padding:18px;border:1px solid #abc;border-radius:12px;margin:16px 0}.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}p,h2,li{overflow-wrap:anywhere}section{min-width:0}@media(max-width:600px){.pair{grid-template-columns:1fr}}</style>",
        "<h1>Table contract review</h1><p>Observed sample types are inference. Expected schema and approved changes are operator-authored contracts. No cell values are included.</p>",
        f"<p>Baseline rows: {before['rowCount']}; current rows: {after['rowCount']}. Invalid rows: {before['invalidRowCount']} → {after['invalidRowCount']}.</p>",
    ]
    delimiter = report.get("delimiterComparison", {})
    parts.append(
        "<p>Parsing delimiter: "
        + html.escape(json.dumps(delimiter.get("before")))
        + " → "
        + html.escape(json.dumps(delimiter.get("after")))
        + "; changed: "
        + html.escape(str(delimiter.get("changed")))
        + " (informational).</p>"
    )
    mappings = report.get("mappingReview", {}).get("mappings", [])
    renamed = {item["from"]: item["to"] for item in mappings}
    targets = set(renamed.values())
    pairs = [(name, renamed.get(name, name)) for name in sorted(old)]
    pairs.extend((name, name) for name in sorted(new.keys() - old.keys() - targets))
    for old_name, new_name in pairs:
        title = old_name if old_name == new_name else old_name + " → " + new_name
        parts.append("<article><h2>" + html.escape(title) + '</h2><div class="pair">')
        for label, item in (("Before", old.get(old_name)), ("After", new.get(new_name))):
            text = (
                "Absent"
                if item is None
                else f"{item['inferred_type']}; {item['non_null_count']} non-null; {item['null_count']} null; maximum length {item['max_length']}"
            )
            parts.append(
                "<section><h3>" + label + "</h3><p>" + html.escape(text) + "</p></section>"
            )
        parts.append("</div></article>")
    if mappings:
        parts.append("<h2>Explicit column mapping</h2><ul>")
        for item in mappings:
            parts.append(
                "<li>"
                + html.escape(item["from"] + " → " + item["to"] + ": " + item["explanation"])
                + "</li>"
            )
        parts.append(
            "</ul><p>Original structural breakingChange is retained. Mapping does not approve type or nullability changes or expected-schema violations.</p>"
        )
    parts.append("<h2>Contract review</h2><ul>")
    for violation in report.get("contractViolations", []):
        parts.append("<li>" + html.escape(str(violation)) + "</li>")
    for change in report.get("approvalReview", {}).get("changes", []):
        parts.append(
            "<li>"
            + html.escape(
                f"{change['column']}: {change['code']} — "
                + (
                    "approved: " + "; ".join(change["explanations"])
                    if change["approved"]
                    else "needs review"
                )
            )
            + "</li>"
        )
    parts.append("</ul></html>")
    return "\n".join(parts)
