"""Bounded source reads and accidental-overwrite-safe report publication."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 10_000_000
MAX_JSON_DEPTH = 128


def read_bytes(path: Path, limit: int | None = None) -> bytes:
    limit = MAX_INPUT_BYTES if limit is None else limit
    selected = path.absolute()
    if any(item.is_symlink() for item in (selected, *selected.parents)):
        raise ValueError("input paths cannot contain symlink components")
    with path.open("rb") as handle:
        content = handle.read(limit + 1)
    if len(content) > limit:
        raise ValueError(f"input exceeds the {limit} byte limit")
    return content


def read_text(path: Path, limit: int | None = None) -> str:
    return read_bytes(path, limit).decode("utf-8-sig")


def load_json(path: Path, limit: int | None = None) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    def finite(value: str) -> None:
        raise ValueError("JSON constants must be finite")

    def finite_float(text: str) -> float:
        number = float(text)
        if not math.isfinite(number):
            raise ValueError("JSON numbers must be finite")
        return number

    try:
        value = json.loads(
            read_text(path, limit),
            object_pairs_hook=unique,
            parse_constant=finite,
            parse_float=finite_float,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds the supported depth") from exc
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, (dict, list)):
            if depth >= MAX_JSON_DEPTH:
                raise ValueError("JSON nesting exceeds the supported depth of 128 containers")
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, depth + 1) for child in children)
    return value


def preflight(outputs: list[Path]) -> None:
    resolved = set()
    for path in outputs:
        selected = path.absolute()
        if any(item.is_symlink() for item in (selected, *selected.parents)):
            raise ValueError("output paths cannot contain symlink components")
        canonical = path.resolve()
        if canonical in resolved or path.exists() or path.is_symlink():
            raise ValueError("outputs must be distinct new files")
        if not path.parent.is_dir():
            raise ValueError("output parent directory must exist")
        resolved.add(canonical)


def write_new(path: Path, content: str) -> None:
    # The explicit symlink check also protects Windows dangling links.
    if path.exists() or path.is_symlink():
        raise ValueError("outputs must be new files")
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)
