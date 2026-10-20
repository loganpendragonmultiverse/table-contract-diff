# Development handoff

Table Contract Diff is a local, value-free structural comparator. It must not export cell values or apply migrations. Version 1 is UTF-8 CSV only; any format or inference expansion requires fixtures for malformed rows, dialect ambiguity, mixed types, and deterministic reports.

## 1.1.0 improvement session

Add expected-schema validation, exact approved-change rules, locale parsing profiles and a value-free HTML comparison.

--expected-schema reads columns keyed by name with type, nullable and optional required (default true), plus allow_extra (default false). --approved-rules is an array of exact code/column/before/after matches with explanation; original breakingChange remains visible and schema violations cannot be approved away. --profiles reads named delimiter/null_values/decimal_separator/thousands_separator/date_format settings, selected with --profile. Dates and numeric conventions are explicit; observed sample types remain inference. --fail-breaking uses effectiveBreakingChange. Reports and schema outputs must be distinct new files; cell values and source CSVs remain untouched.

Local formatting, lint, strict types and regression tests pass. Public release completion requires the protected CI/CodeQL matrix, tagged artifacts and matching Forge catalog/detail deployment.


## 1.2.0 reviewed mapping

Use explicit from/to/explanation JSON only for observed removed-to-added columns. Keep raw structural evidence and original profiles unchanged; approval rules apply to the aligned comparison using current header names. Expected schemas validate current headers. Independent review found no blocking findings in the implementation. Require all protected checks on the final release commit and exact-tag artifact verification before publication.

## 1.2.1 bounded profiling and publication

CSV and auxiliary JSON inputs are limited to 10 MB each; column mappings retain their 1 MB limit. Input paths cannot contain symlinks. Duplicate JSON keys/non-finite constants and malformed CSV quoting fail clearly without exporting cell values; Python CSV parser field-size limits still apply. Profiling aggregates column statistics without retaining a list of all cells, while preserving original-byte source hashes. ISO midnight timestamps remain datetimes, and exact approval rules distinguish booleans from numbers.

All report/schema destinations and rendering are checked before publication; distinct new files use exclusive creation and existing parent directories. A later filesystem failure may leave earlier new reports. This prevents accidental replacement rather than hostile concurrent filesystem manipulation. Long literal headers wrap in HTML and escape in Markdown matrix cells.

Try `table-contract-diff examples/before.csv examples/after.csv --format json --fail-breaking` (exit 1 for the inferred integer-to-decimal change). Retain all existing checks, 90% coverage, value-canary fixtures, browser review and installed wheel/source acceptance. Four principal documents and examples ship in source distributions.

JSON inputs reject nesting beyond 128 containers with an actionable error, including parser recursion failures.

Reports include delimiterComparison before/after/changed evidence in JSON and a labeled delimiter comparison in Markdown and HTML (tabs use an escaped representation). Delimiter changes are informational; they do not themselves create or approve breaking changes.

Wheel installations include synthetic before.csv and after.csv at `<environment>/share/doc/table-contract-diff/examples/` (where `<environment>` is the Python installation or virtual-environment prefix). Pass those paths to `table-contract-diff` outside a source checkout; `--fail-breaking` returns 1 for their intended type change.

JSON numeric overflow (such as `1e400`) is rejected alongside non-finite constants; ordinary finite fractions remain supported.

Canonical ISO week dates (`YYYY-Www-d`) use the same calendar validation on Python 3.10 and newer; invalid week/day combinations remain text. Other inferred date/time forms follow the supported interpreter’s ISO parser and remain heuristics, not an exhaustive date-format validator.
