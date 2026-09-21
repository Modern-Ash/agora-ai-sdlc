---
issue: 94
tested_commit: 0aef9aee3a768a7d010224a9cfc62bdcb39a67a2
timestamp: 2026-09-21
---
# Tests

## Environment
GitHub Actions run #86 on the pull-request merge ref, covering Python 3.11, 3.12 and 3.13 plus the newest supported Agora Core compatibility job.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35612351818

## Exact commands executed by CI
- `uv run --python 3.11 python scripts/verify_all.py`
- `uv run --python 3.12 python scripts/verify_all.py`
- `uv run --python 3.13 python scripts/verify_all.py`
- Core compatibility: install `agora-framework==0.9.1`, install this repository editable without dependencies, then `python -m pytest -q`.

The repository's `verify_all.py` executes lint, Ruff format check, pytest, links, flavor manifest validation, Method Pack validation, executable samples and package/wheel smoke checks.

## Result
PASS on the tested commit.

Python 3.13 full verification evidence:
- lint: passed
- format: passed
- tests: 586 passed, 16 skipped
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
- core-compat with Agora Core 0.9.1: 600 passed, 2 skipped; success

## Failure-path evidence
The new tests exercise invalid schema/version, non-public source scope, affiliation declarations, neutrality violations, unknown canonical mappings, duplicate canonical mappings, duplicate stage ids, capability overlap, and unknown profile/stage lookups.

## Remediation history
- Run #84 found only Ruff formatting differences; corrected.
- Run #85 passed lint/format but exposed the repository vendor-attribution policy for the new reference document; wording was corrected without broadening the policy allowlist.
- Run #86 passed all jobs.

## Cases not executed separately
The focused commands listed in TASK.md were not run as standalone invocations. Their test modules and lint/format coverage were exercised by the full `verify_all.py` CI run.

## Local limitation
The chat execution container did not have a mounted repository checkout and could not resolve GitHub directly. GitHub Actions is therefore the authoritative execution evidence for this implementation.
