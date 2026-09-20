---
sources: [issues #14, #39, #40]
status: draft
---
# Testing contracts

- Planned single entry point `scripts/verify_all.py` (#14) and `agora-ai-sdlc self-test` (#39). **Neither exists yet.**
- Default verification needs no LLM/cloud account or network after dependencies install.
- Tests run in isolated temporary workspaces and never modify the caller repository.
- Package checks must run from the built wheel, not only the source tree.
- Security tests include secret-leak checks and offline resilience (#40).
