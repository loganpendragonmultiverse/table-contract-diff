# Development handoff

Table Contract Diff is a local, value-free structural comparator. It must not export cell values or apply migrations. Version 1 is UTF-8 CSV only; any format or inference expansion requires fixtures for malformed rows, dialect ambiguity, mixed types, and deterministic reports.

## 1.1.0 improvement session

Add expected-schema validation, exact approved-change rules, locale parsing profiles and a value-free HTML comparison.

--expected-schema reads columns keyed by name with type, nullable and optional required (default true), plus allow_extra (default false). --approved-rules is an array of exact code/column/before/after matches with explanation; original breakingChange remains visible and schema violations cannot be approved away. --profiles reads named delimiter/null_values/decimal_separator/thousands_separator/date_format settings, selected with --profile. Dates and numeric conventions are explicit; observed sample types remain inference. --fail-breaking uses effectiveBreakingChange. Reports and schema outputs must be distinct new files; cell values and source CSVs remain untouched.

Local formatting, lint, strict types and regression tests pass. Public release completion requires the protected CI/CodeQL matrix, tagged artifacts and matching Forge catalog/detail deployment.
