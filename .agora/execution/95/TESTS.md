---
issue: 95
tested_commit: b66436521628bf78dc479e9e791f157e04d1f332
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #91 on the pull-request merge ref, covering Python 3.11, 3.12 and 3.13 plus the newest supported Agora Core compatibility job.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35614225775

## Exact commands executed by CI
- `uv run --python 3.11 python scripts/verify_all.py`
- `uv run --python 3.12 python scripts/verify_all.py`
- `uv run --python 3.13 python scripts/verify_all.py`
- Core compatibility: install `agora-framework==0.9.1`, install this repository editable without dependencies, then `python -m pytest -q`.

The repository `verify_all.py` executes lint, Ruff format check, pytest, links, flavor manifest validation, Method Pack validation, executable samples and package/wheel smoke checks.

## Cases executed
The new tests exercise:
- deterministic PASS/PARTIAL/FAIL/NOT_APPLICABLE evaluation;
- required-capability fail-closed behavior;
- optional missing facts as NOT_APPLICABLE;
- required NOT_APPLICABLE converted to FAIL;
- unknown capability facts rejected;
- invalid schema/status/duplicate/missing fields;
- default project fact discovery;
- explicit missing facts path;
- unknown profile normalization;
- human report evidence/reason/remediation/contract output;
- checked-in facts/result schemas;
- no-network evaluation;
- CLI JSON and human modes;
- strict/non-strict exit codes;
- invalid-input exit code 2.

## Result
PASS on the tested implementation commit.

Python 3.13 full verification evidence:
- lint: passed
- format: passed
- tests: 605 passed, 16 skipped
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
- core-compat with Agora Core 0.9.1: 619 passed, 2 skipped; success

## Remediation history
- Run #89 found a Ruff import-order issue; corrected.
- Run #90 found one Ruff formatting difference in the new tests; corrected.
- Run #91 passed all jobs.

## Cases not executed separately
The focused commands in TASK.md were not run as standalone invocations. Their files and behavior were exercised by the broader full `verify_all.py` matrix.

## Evidence
GitHub Actions run #91: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35614225775
