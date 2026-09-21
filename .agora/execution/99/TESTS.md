---
issue: 99
tested_commit:
timestamp: 2026-09-21
---
# Tests

## Environment
Implementation is performed through the GitHub connector. Full execution evidence will come from pull-request CI.

## Exact commands
Pending CI:
- uv run pytest -q tests/test_plans.py tests/test_templates.py tests/conformance/test_aws_original_rules.py tests/test_marketplace_evidence.py
- uv run ruff check src/agora_ai_sdlc/plans.py src/agora_ai_sdlc/artifacts.py tests/test_plans.py
- uv run ruff format --check src/agora_ai_sdlc/plans.py src/agora_ai_sdlc/artifacts.py tests/test_plans.py
- uv run python scripts/check_marketplace_evidence.py
- uv run python scripts/verify_all.py

## Result
Pending CI.
