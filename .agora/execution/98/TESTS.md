---
issue: 98
tested_commit: 547880f0a135d3310e458acd583a227f44512c7b
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #109 on the stacked pull-request merge ref, covering Python 3.11, 3.12 and 3.13 plus the newest supported Agora Core compatibility job.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35620435720

## Exact commands executed by CI
- `uv run --python 3.11 python scripts/verify_all.py`
- `uv run --python 3.12 python scripts/verify_all.py`
- `uv run --python 3.13 python scripts/verify_all.py`
- Core compatibility: install `agora-framework==0.9.1`, install this repository editable without dependencies, then `python -m pytest -q`.

## Cases executed
The new tests verify:
- explicit 0.1.0 and 0.2.0 path resolution;
- unknown versions fail closed;
- 0.2.0 exact lifecycle and terminal state;
- required roles Product Owner + Developer and optional Quality Reviewer declaration;
- exact forward/rework transition graph and gate ids;
- both 0.1.0 and 0.2.0 install and validate through Agora Core;
- the Lifecycle harness keeps 0.1.0 as its default;
- explicit 0.2.0 selection starts work in Inception.

The full suite also exercises all existing lifecycle, samples, profiles, Marketplace evidence, package and wheel behavior.

## Result
PASS on the tested implementation commit.

Python 3.13 full verification:
- lint: passed
- format: passed
- tests: 633 passed, 16 skipped
- links: passed
- manifest: passed
- marketplace-evidence: passed
- packs: 1 active/default pack validated
- samples: 12 existing 0.1.0 samples passed
- package: passed
- overall: all phases passed

Matrix jobs:
- verify (3.11): success
- verify (3.12): success
- verify (3.13): success
- core-compat with Agora Core 0.9.1: 647 passed, 2 skipped; success

## Remediation history
- Run #107 found Ruff formatting in the migration guide; corrected.
- Run #108 exposed that the older supported Core model does not expose optional_roles as a MethodContract attribute; the test was corrected to validate the source contract declaration while retaining Core install/validate coverage.
- Run #109 passed all jobs.

## Evidence
GitHub Actions run #109: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35620435720
