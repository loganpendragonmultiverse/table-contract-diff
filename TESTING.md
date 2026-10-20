# Testing

Run `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, `python -m build`, and `python -m pip_audit .`. Tests cover dialects, types, nullability, malformed rows, additions/removals, reordering, rename suggestions, breaking-change exit behavior, schemas, and hashes.

## 1.1.0 regression acceptance

Run the complete existing suite plus the new regression fixtures. Confirm the documented command produces the selected output, malformed input remains actionable, and source files remain unchanged. Add expected-schema validation, exact approved-change rules, locale parsing profiles and a value-free HTML comparison.


## Explicit mapping regression acceptance

Verify header-only mappings, changed types/nullability, expected-schema checks, exact approval rules, no profile/input mutation, deterministic mapping order, unknown/duplicate/colliding endpoints, identity and cycle rejection, duplicate JSON keys, oversized/malformed mapping files, and escaped HTML headers/explanations. Keep a private-cell canary absent from all output formats. Default unmapped behavior stays unchanged.

## 1.2.1 bounded profiling and publication

CSV and auxiliary JSON inputs are limited to 10 MB each; column mappings retain their 1 MB limit. Input paths cannot contain symlinks. Duplicate JSON keys/non-finite constants and malformed CSV quoting fail clearly without exporting cell values; Python CSV parser field-size limits still apply. Profiling aggregates column statistics without retaining a list of all cells, while preserving original-byte source hashes. ISO midnight timestamps remain datetimes, and exact approval rules distinguish booleans from numbers.

All report/schema destinations and rendering are checked before publication; distinct new files use exclusive creation and existing parent directories. A later filesystem failure may leave earlier new reports. This prevents accidental replacement rather than hostile concurrent filesystem manipulation. Long literal headers wrap in HTML and escape in Markdown matrix cells.

Try `table-contract-diff examples/before.csv examples/after.csv --format json --fail-breaking` (exit 1 for the inferred integer-to-decimal change). Retain all existing checks, 90% coverage, value-canary fixtures, browser review and installed wheel/source acceptance. Four principal documents and examples ship in source distributions.

JSON inputs reject nesting beyond 128 containers with an actionable error, including parser recursion failures.

Reports include delimiterComparison before/after/changed evidence in JSON and a labeled delimiter comparison in Markdown and HTML (tabs use an escaped representation). Delimiter changes are informational; they do not themselves create or approve breaking changes.

Wheel installations include synthetic before.csv and after.csv at `<environment>/share/doc/table-contract-diff/examples/` (where `<environment>` is the Python installation or virtual-environment prefix). Pass those paths to `table-contract-diff` outside a source checkout; `--fail-breaking` returns 1 for their intended type change.

JSON numeric overflow (such as `1e400`) is rejected alongside non-finite constants; ordinary finite fractions remain supported.

Canonical ISO week dates (`YYYY-Www-d`) use the same calendar validation on Python 3.10 and newer; invalid week/day combinations remain text. Other inferred date/time forms follow the supported interpreter’s ISO parser and remain heuristics, not an exhaustive date-format validator.
