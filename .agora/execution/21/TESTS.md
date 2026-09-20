---
issue: 21
tested_commit: working tree on main (post PR #55)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py` passes; 171 tests. `agora-ai-sdlc run-sample new-product` from the source checkout (uv run) and from a wheel installed in a fresh venv outside the repo (package phase) both end `completed` with `agora validate` ok. `tests/test_new_product_sample.py` asserts the exact transition sequence (7 transitions incl. construction->inception rework), 2 blocked gates, expected activity actions, cleanup on success, unknown sample rejected. Sample needs no network, LLM or credentials.
Not executed: Python 3.11/3.13 locally; CI; interruption/failure injection for the sample.
