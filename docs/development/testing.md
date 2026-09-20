# Testing

- Focused checks while developing; full validation before the PR or merge.
- Record exact commands, environment, results, skipped cases with reasons, timestamp and tested commit in `TESTS.md`.
- Fail-closed behavior requires negative tests.
- Default checks must not need network, LLM accounts or cloud accounts.
- Full validation: `uv run python scripts/verify_all.py` (also run by CI on Python 3.11/3.12/3.13). Focused: `uv run pytest tests/<file>`.
- Installed-distribution conformance: `uv run agora-ai-sdlc self-test --json`; see [self-test](../reference/self-test.md).
- Security/resilience checks: `uv run pytest tests/security tests/resilience -q`; see [security and offline resilience](../reference/security-resilience.md). The default suite denies network in the complete self-test, scans an inert canary, distinguishes runtime failures and injects registry failures.
- Never invent commands; add new ones here only when they exist.
