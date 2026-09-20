---
issue: 13
tested_commit: working tree on main (post PR #48)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py` all phases pass (packs phase installs the pack in a throwaway project with Core 0.8.2 and runs `agora validate`). `uv run pytest`: 35 passed, including graph reachability, terminal state, exact edge set, undeclared transitions absent, gate/role references, no vendor terms, Core install+validate, and Core rejecting a pack with an unknown target state.
Not executed: happy-path/rework runs through a live Core work item (deferred to #21), Python 3.11/3.13 locally, CI.
