---
issue: 15
tested_commit: working tree on main (post PR #49)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py`: all phases pass; Core installs and validates the pack with 9 roles. `uv run pytest`: 63 passed (28 new role conformance cases: authorized-action coverage for transitions, gate approvals and criterion stages; denied-action tests; human-only governance-owner; builder never approver).
Not executed: live Core runs with human, AI and delegated actors; test that delegated execution retains the accountable holder in Core records; Python 3.11/3.13 locally.
