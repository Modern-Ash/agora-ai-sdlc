---
issue: 11
tested_commit: working tree on main (post PR #46)
timestamp: 2026-09-20
---
# Tests
Commands: `uv run pytest -q` (21 passed: golden, immutability, one negative per rule, forward-incompatible schema, compatibility message, no network imports); `uv build`; fresh-venv wheel install then `load_packaged_manifest()` + `check_core_compatibility()` succeeded against Core 0.8.2.
Not executed: Python 3.11/3.13 matrix for this change; repository-wide verify command (does not exist, #14).
