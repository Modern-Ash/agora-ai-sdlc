---
issue: 100
tested_commit:
timestamp: 2026-09-21
---
# Tests

## Environment
Implementation is performed through the GitHub connector. Full execution evidence will come from pull-request CI.

## Exact commands
Pending CI:
- uv run pytest -q tests/test_adaptive_planning.py tests/test_plans.py tests/test_cli.py
- uv run ruff check src/agora_ai_sdlc/adaptive_planning.py src/agora_ai_sdlc/cli.py tests/test_adaptive_planning.py
- uv run ruff format --check src/agora_ai_sdlc/adaptive_planning.py src/agora_ai_sdlc/cli.py tests/test_adaptive_planning.py
- uv run python scripts/verify_all.py

## Result
Pending CI.
