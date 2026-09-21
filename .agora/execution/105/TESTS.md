---
issue: 105
tested_commit: e3277a415c306c29d00713ae7164339c702df041
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #151 on PR #123 against main.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35630541724

## Verification
- Python 3.11 verify_all.py: success
- Python 3.12 verify_all.py: success
- Python 3.13 verify_all.py: success
- Core compatibility against agora-framework 0.9.1: success

Python 3.13:
- lint: passed
- format: passed
- tests: 724 passed, 18 skipped
- links: passed
- manifest: passed
- marketplace-evidence: current
- packs: 1 validated
- samples: 13 passed
- package/wheel: passed

Core compatibility:
- 740 passed, 2 skipped

## Functional cases covered
- valid three-repository artifact;
- API/event/schema contract validation;
- provider-neutral repository ids and opaque refs;
- unknown dependencies require reason and explicit unknowns;
- exact-revision approval and stale approval rejection;
- reviewer/owner separation;
- Unit/Plan/Bolt Plan trace binding;
- generic traceability integration;
- enterprise approved-impact-analysis evidence;
- offline cross-repository sample.

## Remediation history
- Initial CI exposed Ruff formatting differences.
- Next run exposed the hard-coded executable sample count after adding cross-repo-impact.
- Updated the offline sample inventory expectation from 12 to 13.
- Run #151 passed the full matrix.

## Evidence
Run #151: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35630541724
