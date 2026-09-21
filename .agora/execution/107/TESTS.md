---
issue: 107
status: pending
updated_at: 2026-09-21
---
# Tests

Automated verification is pending GitHub Actions. The current execution environment cannot clone or install the repository because outbound DNS/network access is unavailable outside the GitHub connector.

## Required focused verification
- uv run pytest -q tests/test_enterprise_controls.py
- uv run ruff check src/agora_ai_sdlc/enterprise_controls.py tests/test_enterprise_controls.py
- uv run ruff format --check src/agora_ai_sdlc/enterprise_controls.py tests/test_enterprise_controls.py

## Required full verification
- uv run python scripts/verify_all.py
