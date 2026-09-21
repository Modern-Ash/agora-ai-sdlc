---
issue: 96
tested_commit: 6eebc988063208acc919d457ad9a696d16015bc9
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #97 on the stacked pull-request merge ref, covering Python 3.11, 3.12 and 3.13 plus the newest supported Agora Core compatibility job.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35616365363

## Exact commands executed by CI
- `uv run --python 3.11 python scripts/verify_all.py`
- `uv run --python 3.12 python scripts/verify_all.py`
- `uv run --python 3.13 python scripts/verify_all.py`
- Core compatibility: install `agora-framework==0.9.1`, install this repository editable without dependencies, then `python -m pytest -q`.

The repository `verify_all.py` executes lint, Ruff format check, pytest, links, flavor manifest validation, Method Pack validation, executable samples and package/wheel smoke checks.

## Cases executed
The #96 tests cover:
- complete rule coverage for every aws-original capability;
- explicit base-method vs agora-additive classification;
- current-repository golden PASS/PARTIAL/FAIL/NOT_APPLICABLE snapshot;
- evidence/remediation presence;
- additive governance excluded from base scoring;
- checked-in rule schema contract;
- unknown check types;
- missing rule for a declared profile capability;
- undeclared rule capability;
- repository path escape rejection;
- offline/no-network derivation;
- `conformance aws-original --derive` JSON/human paths;
- strict mode;
- invalid derive/facts combinations and unsupported provider derivation.

## Result
PASS on the tested implementation commit.

Python 3.13 full verification evidence:
- lint: passed
- format: passed
- tests: 617 passed, 16 skipped
- links: passed
- manifest: passed
- packs: 1 pack validated
- samples: 12 samples passed
- package: passed
- overall: all phases passed

Matrix jobs:
- verify (3.11): success
- verify (3.12): success
- verify (3.13): success
- core-compat with Agora Core 0.9.1: 631 passed, 2 skipped; success

## Remediation history
- Run #93 found import ordering in conformance exports; corrected.
- Runs #94/#95 exposed remaining Ruff formatting; corrected.
- Run #96 reached behavioral tests and exposed one golden expectation: governed operational remediation is currently PARTIAL rather than PASS; the golden was corrected to match actual repository evidence.
- Run #97 passed all jobs.

## Current fidelity golden
- PASS: 11 capabilities
- PARTIAL: 10 capabilities
- FAIL: 1 capability (`recursive-planning`)
- NOT_APPLICABLE: 1 optional capability (`prfaq`)

## Cases not executed separately
The focused commands in TASK.md were not run as standalone invocations. Their modules were exercised by the complete CI matrix.

## Evidence
GitHub Actions run #97: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35616365363
