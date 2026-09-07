from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .contracts import validate_profile


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    position: int
    inferred_type: str
    nullable: bool
    null_count: int
    non_null_count: int
    max_length: int


def _cell_type(value: str) -> str:
    clean = value.strip()
    if not clean:
        return "null"
    if clean.lower() in {"true", "false", "yes", "no"}:
        return "boolean"
    if re.fullmatch(r"[+-]?\d+", clean):
        return "integer"
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)", clean):
        return "decimal"
    try:
        parsed = datetime.fromisoformat(clean.replace("Z", "+00:00"))
        return "datetime" if parsed.time().isoformat() != "00:00:00" or "T" in clean else "date"
    except ValueError:
        try:
            date.fromisoformat(clean)
            return "date"
        except ValueError:
            return "text"


def _merge_types(types: set[str]) -> str:
    types.discard("null")
    if not types:
        return "unknown"
    if types <= {"integer", "decimal"}:
        return "decimal" if "decimal" in types else "integer"
    if types <= {"date", "datetime"}:
        return "datetime" if "datetime" in types else "date"
    return next(iter(types)) if len(types) == 1 else "mixed"


def profile_csv(path: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = validate_profile({} if profile is None else profile)
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    if not text.strip():
        raise ValueError("CSV is empty")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), delimiter=settings.get("delimiter", dialect.delimiter))
    try:
        headers = next(reader)
    except StopIteration as exc:  # pragma: no cover - guarded by the non-empty check
        raise ValueError("CSV is empty") from exc
    if not headers or any(not header.strip() for header in headers):
        raise ValueError("every column requires a non-empty header")
    if len(set(headers)) != len(headers):
        raise ValueError("duplicate headers are not supported")
    values: list[list[str]] = [[] for _ in headers]
    row_count = 0
    invalid_rows = 0
    for row in reader:
        row_count += 1
        if len(row) != len(headers):
            invalid_rows += 1
            continue
        for index, value in enumerate(row):
            values[index].append(value)
    columns = []
    null_values = set(settings.get("null_values", [""]))

    def cell_type(value: str) -> str:
        clean = value.strip()
        if clean in null_values:
            return "null"
        if not clean:
            return "text"
        if settings.get("date_format"):
            try:
                datetime.strptime(clean, settings["date_format"]).date()
                return "date"
            except ValueError:
                pass
        number = clean
        if settings.get("thousands_separator"):
            number = number.replace(settings["thousands_separator"], "")
        number = number.replace(settings.get("decimal_separator", "."), ".")
        kind = _cell_type(number)
        return kind if kind in ("integer", "decimal") else _cell_type(clean)

    for index, (header, column) in enumerate(zip(headers, values, strict=True)):
        null_count = sum(value.strip() in null_values for value in column)
        columns.append(
            ColumnProfile(
                header,
                index,
                _merge_types({cell_type(value) for value in column}),
                bool(null_count),
                null_count,
                len(column) - null_count,
                max((len(value) for value in column), default=0),
            )
        )
    return {
        "schemaVersion": 1,
        "source": path.name,
        "sourceSha256": hashlib.sha256(raw).hexdigest(),
        "encoding": "utf-8",
        "delimiter": settings.get("delimiter", dialect.delimiter),
        "parsingProfile": settings,
        "rowCount": row_count,
        "invalidRowCount": invalid_rows,
        "columns": [asdict(column) for column in columns],
    }


def compare_profiles(baseline: dict[str, object], current: dict[str, object]) -> dict[str, Any]:
    baseline_columns = baseline["columns"]
    current_columns = current["columns"]
    assert isinstance(baseline_columns, list) and isinstance(current_columns, list)
    before = {str(item["name"]): item for item in baseline_columns}
    after = {str(item["name"]): item for item in current_columns}
    removed = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changes: list[dict[str, object]] = []
    for name in sorted(set(before) & set(after)):
        old, new = before[name], after[name]
        for field, code in (
            ("inferred_type", "type-changed"),
            ("nullable", "nullability-changed"),
            ("position", "position-changed"),
        ):
            if old[field] != new[field]:
                changes.append(
                    {"code": code, "column": name, "before": old[field], "after": new[field]}
                )
    rename_candidates = []
    for old_name in removed:
        for new_name in added:
            score = round(SequenceMatcher(None, old_name.lower(), new_name.lower()).ratio(), 3)
            if (
                score >= 0.6
                and before[old_name]["inferred_type"] == after[new_name]["inferred_type"]
            ):
                rename_candidates.append({"from": old_name, "to": new_name, "similarity": score})
    return {
        "schemaVersion": 1,
        "baselineSha256": baseline["sourceSha256"],
        "currentSha256": current["sourceSha256"],
        "addedColumns": added,
        "removedColumns": removed,
        "changes": changes,
        "renameCandidates": rename_candidates,
        "invalidRowDelta": int(str(current["invalidRowCount"]))
        - int(str(baseline["invalidRowCount"])),
        "breakingChange": bool(
            removed
            or any(item["code"] in {"type-changed", "nullability-changed"} for item in changes)
        ),
    }
