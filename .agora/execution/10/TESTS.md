---
issue: 10
tested_commit: working tree on main (post PR #45)
timestamp: 2026-09-20
---
# Tests

## Commands
`uv sync`; `uv run pytest -q`; `uv run --isolated --python {3.11,3.12,3.13} pytest -q`; `uv build`; `unzip -l` on wheel; `tar tzf` on sdist; fresh venv install of the wheel + `agora-ai-sdlc --version`; `uv pip list` grep for provider SDKs.

## Result
All passed: 3 tests on 3.11/3.12/3.13; wheel and sdist build; assets (5 directories) present in both; installed wheel runs `--version`; no openai/anthropic/boto in the environment.

## Not executed
Package metadata range check against a newer agora-framework (only 0.8.2 exists).
