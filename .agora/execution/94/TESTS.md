---
issue: 94
tested_commit:
timestamp: 2026-09-21
---
# Tests

## Environment
Implementation was performed through the GitHub connector. The execution container cannot resolve github.com, so a complete checkout cannot be materialized there before the pull request.

## Exact commands
Pending GitHub Actions execution:
- uv run pytest -q tests/test_compatibility_profiles.py tests/conformance/test_self_test.py
- uv run ruff check src/agora_ai_sdlc/compatibility_profiles.py tests/test_compatibility_profiles.py
- uv run ruff format --check src/agora_ai_sdlc/compatibility_profiles.py tests/test_compatibility_profiles.py
- uv run python scripts/verify_all.py

## Cases executed
No local repository checks yet. Contract code and tests were inspected against the existing repository patterns.

## Result
Pending CI.

## Cases not executed
Focused and full repository verification.

## Reason for omission
The available execution container has no DNS/network path to GitHub and the repository is not mounted locally. The pull-request CI is the repository's authoritative full verification path and will run the same verify_all.py entry point across supported Python versions.

## Evidence
CI evidence will be recorded here after the draft pull request triggers the workflow.
