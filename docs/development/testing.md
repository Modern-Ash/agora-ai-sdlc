# Testing

- Focused checks while developing; full validation before the PR or merge.
- Record exact commands, environment, results, skipped cases with reasons, timestamp and tested commit in `TESTS.md`.
- Fail-closed behavior requires negative tests.
- Default checks must not need network, LLM accounts or cloud accounts.
- **No validation commands exist yet** (verification pipeline: issue #14). Until then use inspection and document it. Never invent commands; once #14 lands, list the real entry point here.
