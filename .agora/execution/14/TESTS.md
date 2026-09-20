---
issue: 14
tested_commit: working tree on main (post PR #47)
timestamp: 2026-09-20
---
# Tests
`uv run python scripts/verify_all.py` passed all phases locally (Python 3.14 default). Injected broken link (`zz.md`) made the links phase fail with phase name and recovery, non-zero exit; removed afterwards. Unit tests cover links, malformed manifest, empty packs/samples, failure reporting. Package phase builds the wheel and loads the manifest from a venv outside the repo.
Not executed: CI workflow itself (runs on PR), cold-cache CI, 3.11/3.13 locally, `agora pack validate` path (no packs exist).
