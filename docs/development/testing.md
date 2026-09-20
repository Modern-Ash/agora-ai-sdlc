# Testing

- Focused checks while developing; full validation before the PR or merge.
- Record exact commands, environment, results, skipped cases with reasons, timestamp and tested commit in `TESTS.md`.
- Fail-closed behavior requires negative tests.
- Default checks must not need network, LLM accounts or cloud accounts.
- Full validation: `uv run python scripts/verify_all.py` (also run by CI on Python 3.11/3.12/3.13). Focused: `uv run pytest tests/<file>`.
- Never invent commands; add new ones here only when they exist.
