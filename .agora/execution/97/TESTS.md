---
issue: 97
tested_commit:
timestamp: 2026-09-21
---
# Tests

## Environment
Implementation is performed through the GitHub connector. Full execution evidence will come from pull-request CI.

## Exact commands
Pending CI:
- uv run pytest -q tests/test_marketplace_evidence.py
- uv run python scripts/check_marketplace_evidence.py
- uv run ruff check src/agora_ai_sdlc/marketplace_evidence.py scripts/check_marketplace_evidence.py tests/test_marketplace_evidence.py
- uv run ruff format --check src/agora_ai_sdlc/marketplace_evidence.py scripts/check_marketplace_evidence.py tests/test_marketplace_evidence.py
- uv run python scripts/verify_all.py

## Cases executed
Contract/code inspection only; automated execution pending CI.

## Result
Pending.

## Cases not executed
Focused and full repository verification.

## Reason for omission
The active chat environment does not provide a mounted checkout of this repository. Pull-request CI is the authoritative verification path.

## Evidence
Will be updated after CI completes.
