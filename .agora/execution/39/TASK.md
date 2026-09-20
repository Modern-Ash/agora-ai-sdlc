---
issue: 39
epic: 7
title: Build single-command AI-SDLC conformance harness
repository: Modern-Ash/agora-ai-sdlc
base_commit: 228bebe
status: review
risk: high
context_size: large
planner: Codex
created_at: 2026-09-20
---
# Task: Build single-command AI-SDLC conformance harness

## Objective
Provide `agora-ai-sdlc self-test` as a deterministic, credential-free check of every bundled profile and executable sample, plus the shipped Method Pack, policies, templates, and JSON contracts.

## Allowed paths
- `.agora/execution/39/`
- `src/agora_ai_sdlc/conformance/`
- `src/agora_ai_sdlc/cli.py`
- `contracts/conformance/`
- `tests/conformance/`
- `tests/test_cli.py`
- `scripts/verify_all.py`
- `docs/reference/self-test.md`
- `docs/development/testing.md`
- `README.md`

## Forbidden changes
- Agora Core lifecycle or persistence contracts
- Existing Method Pack, profile, policy, sample, or provider semantics
- Network calls, credentials, provider SDKs, or environment dumps

## Functional requirements
- Run from one CLI command without an initialized caller project.
- Discover packaged assets rather than maintaining a duplicate sample/profile list.
- Execute every bundled sample and a real Core AI-SDLC role/lifecycle case in isolated temporary repositories.
- Exercise human and AI holders, a represented-swarm delegated holder, and rejection of service holders where unsupported.
- Emit progress only on stderr and an optional schema-versioned JSON summary on stdout.
- Return non-zero on failure, retain/report failed workspace, and clean successful or interrupted workspaces.
- Execute successfully from the installed wheel.

## Acceptance criteria
- [x] One command verifies all shipped assets.
- [x] Caller repository is never modified.
- [x] Failed workspace is reported; successful and interrupted workspaces are cleaned.
- [x] Installed-wheel execution passes.
- [x] Success, injected failure, interruption, and JSON contract have deterministic tests.

## Focused verification
- `uv run pytest tests/conformance/test_self_test.py tests/test_cli.py tests/test_verify_all.py -q`
- `uv run ruff check src/agora_ai_sdlc/conformance src/agora_ai_sdlc/cli.py tests/conformance/test_self_test.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- #13 repository verification pipeline
- #21 executable Method Pack sample
- Agora Core 0.8.2 public workspace, actor, role, and lifecycle APIs

## Clarifications
Service actors are not allowed by any current AI-SDLC role. Conformance therefore exercises their required fail-closed rejection rather than inventing a service-compatible role.

## Completion evidence
Implementation and verification complete; independent review pending.
