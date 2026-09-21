---
issue: 97
tested_commit: 425471fce7ee1ed978d383589925697afd16ad6c
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #103 on the stacked pull-request merge ref, covering Python 3.11, 3.12 and 3.13 plus the newest supported Agora Core compatibility job.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35618483857

## Exact commands executed by CI
- `uv run --python 3.11 python scripts/verify_all.py`
- `uv run --python 3.12 python scripts/verify_all.py`
- `uv run --python 3.13 python scripts/verify_all.py`
- Core compatibility: install `agora-framework==0.9.1`, install this repository editable without dependencies, then `python -m pytest -q`.

The repository verification now includes a `marketplace-evidence` phase that regenerates and compares the checked-in compatibility matrix.

## Cases executed
The issue #97 tests cover:
- deterministic matrix generation;
- checked-in generated file equality;
- AWS-original / LG-enterprise / Agora-open columns;
- LG TARGET_ONLY boundary;
- preservation of AWS PARTIAL/FAIL gaps;
- forbidden endorsement/certification implications;
- missing generated file failure;
- stale generated file failure;
- current generated file success;
- existing Marketplace document inventory and claim-substantiation consistency including C10.

## Result
PASS on the tested implementation commit.

Python 3.13 full verification:
- lint: passed
- format: passed
- tests: 627 passed, 16 skipped
- links: passed
- manifest: passed
- marketplace-evidence: passed (compatibility evidence matrix is current)
- packs: 1 pack validated
- samples: 12 samples passed
- package: passed
- overall: all phases passed

Matrix jobs:
- verify (3.11): success
- verify (3.12): success
- verify (3.13): success
- core-compat with Agora Core 0.9.1: 641 passed, 2 skipped; success

## Remediation history
- Run #101 exposed a Ruff import convention in the new test module; corrected.
- Run #102 then exposed the existing Marketplace inventory/claim-count tests, which were deliberately updated to include the generated document and claim C10.
- Run #103 passed all jobs.

## Evidence
GitHub Actions run #103: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35618483857
