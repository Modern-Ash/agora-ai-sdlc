---
sources: [issues #14, #39, #40]
status: draft
---
# Testing contracts

- `scripts/verify_all.py` exists (#14, run with `uv run python scripts/verify_all.py`). `agora-ai-sdlc self-test` (#39) does **not** exist yet; `agora-ai-sdlc run-sample new-product` (#21) does.
- Default verification needs no LLM/cloud account or network after dependencies install.
- Tests run in isolated temporary workspaces and never modify the caller repository.
- Package checks must run from the built wheel, not only the source tree.
- Security tests include secret-leak checks and offline resilience (#40).
