---
issue: 105
tested_commit:
timestamp: 2026-09-21
---
# Tests

## Environment
Implementation is performed through the GitHub connector. Full execution evidence will come from pull-request CI.

## Exact commands
Pending CI:
- uv run pytest -q tests/test_impact_analysis.py tests/test_templates.py tests/test_enterprise_reviews.py
- uv run ruff check src/agora_ai_sdlc/impact_analysis.py src/agora_ai_sdlc/artifacts.py tests/test_impact_analysis.py
- uv run ruff format --check src/agora_ai_sdlc/impact_analysis.py src/agora_ai_sdlc/artifacts.py tests/test_impact_analysis.py
- uv run python scripts/verify_all.py

## Result
Pending CI.
