# Table Contract Diff

Table Contract Diff compares two CSV files as data contracts without copying cell values into its reports.

It detects added, removed, reordered, renamed, type-shifted, and newly nullable columns; delimiter changes; malformed-row changes; and deterministic schema fingerprints. Optional schema exports contain structural counts and maximum lengths but no cell values.

## Three-minute start

```bash
python -m pip install .
table-contract-diff previous.csv current.csv --output contract-review.md
table-contract-diff previous.csv current.csv --format json --fail-breaking
```

## Scope and limitations

- Version 1 accepts UTF-8 CSV-family files with comma, semicolon, tab, or pipe delimiters.
- Inference samples the complete valid input but cannot know business meaning or whether a change is acceptable.
- Rename candidates are suggestions based on header similarity and inferred type; they are never applied automatically.
- Dates use ISO-style parsing. Locale-specific numbers and dates may be classified as text.
- Input files remain unchanged; there is no network access, upload, telemetry, spreadsheet execution, or formula evaluation.

Python 3.10+ on Windows, macOS, and Linux. Current release: **v1.1.0**. Pull requests are reviewed. MIT licensed.

## Version 1.1.0: reviewed improvements

Add expected-schema validation, exact approved-change rules, locale parsing profiles and a value-free HTML comparison.

```bash
table-contract-diff before.csv after.csv --format html --output review.html
```

--expected-schema reads columns keyed by name with type, nullable and optional required (default true), plus allow_extra (default false). --approved-rules is an array of exact code/column/before/after matches with explanation; original breakingChange remains visible and schema violations cannot be approved away. --profiles reads named delimiter/null_values/decimal_separator/thousands_separator/date_format settings, selected with --profile. Dates and numeric conventions are explicit; observed sample types remain inference. --fail-breaking uses effectiveBreakingChange. Reports and schema outputs must be distinct new files; cell values and source CSVs remain untouched.


## Reviewed column mapping (1.2.0 source candidate)

Pass `--column-mapping mapping.json` to align explicitly reviewed removed-to-added columns. The JSON is an array, for example:

```json
[{"from": "customer_id", "to": "customer_identifier", "explanation": "Reviewed identifier header change"}]
```

Only exact observed removed/added names are accepted, with one-to-one endpoints and non-empty explanations. Duplicate JSON keys, unknown fields, missing names, identity mappings, chains, cycles and collisions are rejected. No similarity suggestion is applied automatically. Empty arrays leave comparison unchanged. Inputs and exported source profiles remain unchanged.

The original `addedColumns`, `removedColumns`, `changes` and `breakingChange` stay visible. `mappingReview` records the mapping and aligned comparison. `approvalReview` and `effectiveBreakingChange` use that aligned comparison, so an explicit header-only mapping can pass `--fail-breaking`. Type and nullability changes still need their own exact approved rules, using the current column name. Expected schemas always validate the actual current headers and cannot be overridden by a mapping. HTML pairs mapped columns and escapes names/explanations; reports never include cell values. Mapping files over 1 MB are refused.
