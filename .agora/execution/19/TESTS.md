---
issue: 19
tested_commit: working tree on main (post PR #53)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py` passes; 143 passed, 1 skipped (README index). Coverage: every gate-required artifact kind has a template; all 13 issue-listed kinds parse; front-matter/schema/kind/version/id rules; missing-section; golden chain parse and traceability; dangling, missing-parent, wrong-parent-kind, duplicate-id, uncovered and unknown criteria; no provider prompt syntax markers. Wheel contains templates.
Not executed: model-fill test ("a model can fill templates using only documented semantics" is asserted by docs, not tested); wiring into gates or verify_all; Python 3.11/3.13; CI.
