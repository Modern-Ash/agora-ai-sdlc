# Tests — #253
- `uv run --frozen pytest tests -q` → 1102 passed, 24 skipped, 1 failed.
- The 1 failure (`test_calculator_brief_happy_path_reaches_completed`) also fails on clean origin/main (verified by stashing changes); unrelated.
- New: `tests/test_runtime_domain.py` (normalization, fail-closed diagnostics, discovery split, selection binding).
- `scripts/verify_all.py` recorded below when run.
