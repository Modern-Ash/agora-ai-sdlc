---
issue: 17
tested_commit: working tree on main (post PR #51)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py` passes; 97 tests. `tests/test_early_gates.py` drives real Core 0.8.2: positives for the three gates; one negative per obligation (missing artifact, criterion stage, architect approval, stale clarification); blocker text asserted actionable; reopen clears prior-revision artifacts/approvals/criteria; a test documents that approvals are not gate-scoped.
Not executed: profile composition test; per-gate PO-approval negatives (not enforceable in Core 0.8.2); Python 3.11/3.13; CI.
