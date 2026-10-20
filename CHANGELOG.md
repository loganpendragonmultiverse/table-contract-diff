# Changelog

## 1.2.1 - 2026-10-20

- Bound input reads, aggregate CSV column statistics and report malformed quoting/oversized fields clearly.
- Preserve midnight datetime inference and canonical ISO week dates across supported Python versions; distinguish boolean from numeric approval values.
- Protect existing/competing outputs, escape literal Markdown cells and wrap long HTML headers.
- Ship complete release handoffs and synthetic examples in wheel and source installations.
- Expose informational before/after delimiter changes in JSON, Markdown and HTML without changing structural breaking rules.

JSON inputs reject nesting beyond 128 containers with an actionable error, including parser recursion failures.

- Reject JSON numeric overflow while preserving finite fractions.

## 1.2.0 - 2026-10-15

- Add explicit one-to-one removed-to-added column mappings with required explanations and aligned structural comparison.
- Retain original changes and breaking-change evidence; mapped type/nullability changes and expected-schema violations remain independently reviewable.

## 1.1.0 - 2026-09-07

- Add expected-schema validation, exact approved-change rules, locale parsing profiles and a value-free HTML comparison.
- Added regression coverage for the audited behavior and invalid inputs.

## 1.0.0 - 2026-08-10

- Added value-free CSV profiling with inferred types, nullability, dialect, row evidence, and hashes.
- Added contract comparison for columns, types, order, nullability, malformed rows, and rename candidates.
- Added JSON, Markdown, and portable schema output plus CI breaking-change behavior.
