---
issue: 100
tested_commit: 51b8c779d100c28865a11eb074281508c37a433c
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #129 on draft PR #117, stacked on #99.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35624843952

## Verification
- Python 3.11 verify_all.py: success
- Python 3.12 verify_all.py: success
- Python 3.13 verify_all.py: success
- Core compatibility against agora-framework 0.9.1: success

Python 3.13:
- lint: passed
- format: passed
- tests: 660 passed, 16 skipped
- links: passed
- manifest: passed
- marketplace-evidence: current
- packs: 1 validated
- samples: 12 passed
- package/wheel: passed

Core compatibility:
- 674 passed, 2 skipped

## Functional cases covered
- one Method Pack 0.2.0 lifecycle shared by all six pathways;
- trivial-change optional design skipping at minimal/standard depth;
- new-product standard baseline;
- brownfield static/dynamic semantic elevation;
- regulated security/testing/deployment/observability obligations;
- adoption profile/depth can only increase obligations;
- missing/skip mandatory steps fail closed;
- unknown pathway steps fail closed;
- pending/rejected plans are not authorized;
- plan-validate CLI success/error behavior;
- adaptive pathway assets are included in bundled self-test.

## Remediation history
- #122 found unused/import ordering issues.
- #125 found Ruff formatting differences.
- #126 exposed that new pathway YAML contracts were not registered with the packaged self-test inventory.
- Added versioned pathway schemas to self-test discovery and validated every packaged pathway.
- #129 passed the complete matrix.

## Evidence
Run #129: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35624843952
