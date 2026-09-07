# Testing

Run `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, `python -m build`, and `python -m pip_audit .`. Tests cover dialects, types, nullability, malformed rows, additions/removals, reordering, rename suggestions, breaking-change exit behavior, schemas, and hashes.

## 1.1.0 regression acceptance

Run the complete existing suite plus the new regression fixtures. Confirm the documented command produces the selected output, malformed input remains actionable, and source files remain unchanged. Add expected-schema validation, exact approved-change rules, locale parsing profiles and a value-free HTML comparison.
