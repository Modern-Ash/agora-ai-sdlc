---
issue: 16
tested_commit: working tree on main (post PR #50)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py`: all phases pass. `uv run pytest`: 79 passed. New `tests/test_lifecycle.py` drives real Agora Core 0.8.2 (local, no network/LLM): happy path through all 5 forward transitions; rejected gates leave state unchanged; unauthorized actors get PermissionError; undeclared transition rejected; each of the 3 rework edges requires a `rework-record` and keeps prior artifacts/evidence; completed work is immutable; reopen by product-owner creates revision+1 with reason and actor recorded; reopen before completion or by a non-terminal role is rejected.
Not executed: reconstruction of full rework history from Core records (only outcomes asserted); Python 3.11/3.13 locally; CI.
