---
issue: 18
tested_commit: working tree on main (post PR #52)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py` passes; 113 tests. `tests/test_late_gates.py` drives Core 0.8.2: positives; one negative per obligation for build-verified and completion; failed test evidence blocks build; failed-only security-scan blocks completion; reopen clears evidence/artifacts so prior-revision deployment evidence cannot satisfy completion; approvals register contains the accountable actor.
Not executed: severity/profile-based blocking (#20); evidence content-digest binding; PO-approval negative at completion (approvals are not gate-scoped); Python 3.11/3.13; CI.
