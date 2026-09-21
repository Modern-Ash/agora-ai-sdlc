---
issue: 106
tested_commit:
timestamp: 2026-09-21
---
# Tests

Pending pull-request CI.

Focused:
- uv run pytest -q tests/test_change_management.py tests/test_domain_knowledge.py tests/test_templates.py
- uv run ruff check src/agora_ai_sdlc/change_management.py src/agora_ai_sdlc/domain_knowledge.py tests/test_change_management.py tests/test_domain_knowledge.py
- uv run ruff format --check src/agora_ai_sdlc/change_management.py src/agora_ai_sdlc/domain_knowledge.py tests/test_change_management.py tests/test_domain_knowledge.py

Full:
- uv run python scripts/verify_all.py
