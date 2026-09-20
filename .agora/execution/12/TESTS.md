---
issue: 12
timestamp: 2026-09-20
---
# Tests

`uv run python scripts/verify_all.py` — all phases passed (548 passed, 2 skipped), including the link check and `tests/test_architecture_docs.py` (terminology uniqueness, ADR structure, vendor-name lint, AWS-not-dependency wording).

Omitted: the AWS blog URL was not fetched (no network check); the mapping cites only phase and concept names.
