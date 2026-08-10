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

Python 3.10+ on Windows, macOS, and Linux. Current release: **v1.0.0**. Pull requests are reviewed. MIT licensed.
