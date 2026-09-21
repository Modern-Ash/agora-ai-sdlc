---
issue: 99
tested_commit: 88c5000a6a6d76b7fe830464d3c9582baa25ee65
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #118 on PR #116, retargeted to main after #98 promotion.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35623380104

## Verification
- Python 3.11 verify_all.py: success
- Python 3.12 verify_all.py: success
- Python 3.13 verify_all.py: success
- Core compatibility against agora-framework 0.9.1: success

Python 3.13:
- lint: passed
- format: passed
- tests: 645 passed, 16 skipped
- links: passed
- manifest: passed
- marketplace-evidence: current
- packs: 1 validated
- samples: 12 passed
- package/wheel: passed

Core compatibility:
- 659 passed, 2 skipped

## Remediation history
Earlier runs correctly exposed the stale AWS conformance expectation after recursive planning moved from FAIL to PASS. The assertion was updated from overall FAIL to PARTIAL, matching the generated golden and Marketplace evidence.

## Evidence
Run #118: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35623380104
