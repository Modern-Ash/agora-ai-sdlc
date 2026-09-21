---
issue: 96
tested_commit:
timestamp: 2026-09-21
---
# Tests

## Environment
Implementation is performed through the GitHub connector. Full execution evidence will come from pull-request CI on the stacked branch.

## Exact commands
Pending CI:
- uv run pytest -q tests/conformance/test_aws_original_rules.py tests/test_cli.py
- uv run ruff check src/agora_ai_sdlc/conformance/aws_original.py src/agora_ai_sdlc/cli.py tests/conformance/test_aws_original_rules.py tests/test_cli.py
- uv run ruff format --check src/agora_ai_sdlc/conformance/aws_original.py src/agora_ai_sdlc/cli.py tests/conformance/test_aws_original_rules.py tests/test_cli.py
- uv run python scripts/verify_all.py

## Cases executed
Contract/code inspection only; automated execution pending CI.

## Result
Pending.

## Cases not executed
Focused and full repository verification.

## Reason for omission
The active chat execution environment does not provide a mounted checkout of this GitHub repository. Pull-request CI is the authoritative verification path.

## Evidence
Will be updated after CI completes.
