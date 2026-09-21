---
issue: 106
tested_commit: 305c24646b6d8d6a1c23880db018ed7e4c511871
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #157 on PR #124 against main.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35631799036

## Verification
- Python 3.11 verify_all.py: success
- Python 3.12 verify_all.py: success
- Python 3.13 verify_all.py: success
- Core compatibility against agora-framework 0.9.1: success

Python 3.13:
- lint: passed
- format: passed
- tests: 756 passed, 18 skipped
- links: passed
- manifest: passed
- marketplace-evidence: current
- packs: 1 validated
- samples: 15 passed
- package/wheel: passed

Core compatibility:
- 772 passed, 2 skipped

## Remediation history
- First run exposed Ruff formatting in the new modules/tests.
- Formatting was corrected and the final run passed the full matrix.

## Evidence
Run #157: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35631799036
