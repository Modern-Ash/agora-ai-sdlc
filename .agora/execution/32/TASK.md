---
issue: 32
epic: 5
title: Implement Starter profile and guided bootstrap
repository: Modern-Ash/agora-ai-sdlc
base_commit: 3bf8571
status: review
risk: high
context_size: medium
planner: Codex
created_at: 2026-09-20
---
# Task: Implement Starter profile and guided bootstrap

## Objective
Bootstrap one existing or fresh repository into a deterministic one-team AI-SDLC pilot after an explicit preview and confirmation.

## Allowed paths
- `.agora/execution/32/`
- `profiles/starter/`
- `src/agora_ai_sdlc/starter.py`
- `src/agora_ai_sdlc/cli.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `samples/starter/`
- `samples/README.md`
- `tests/test_starter.py`
- `tests/test_starter_sample.py`
- `docs/profiles/starter.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Functional requirements
- One repository and one swarm using standard depth and `ai-sdlc@0.1.0`.
- Distinct human Product Owner and Quality Reviewer.
- Human execution plus at most two explicit AI runtimes.
- Pure deterministic preview before any write.
- Interactive confirmation and explicit non-interactive apply.
- Supported Core initialization, actors, assignments, swarm, and first Unit of Work.

## Acceptance criteria
- [x] Bootstrap works for fresh and existing repositories.
- [x] Interactive cancellation writes nothing.
- [x] Explicit non-interactive configuration is deterministic.
- [x] Result validates and contains a first Unit of Work in readiness.

## Verification
- `uv run pytest tests/test_starter.py tests/test_starter_sample.py -q`
- `uv run ruff check src/agora_ai_sdlc/starter.py src/agora_ai_sdlc/cli.py tests/test_starter.py tests/test_starter_sample.py samples/starter/run.py`
- `uv run python scripts/verify_all.py`

## Constraints
No credentials, provider SDKs, external CLIs, implicit runtime discovery, or unsupported Core configuration.
