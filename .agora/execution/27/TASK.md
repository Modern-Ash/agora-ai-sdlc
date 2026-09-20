---
issue: 27
epic: 4
title: Implement GitHub delivery profile
repository: Modern-Ash/agora-ai-sdlc
base_commit: df0d977
status: review
risk: medium
context_size: medium
budget:
  max_input_tokens: 30000
  max_output_tokens: 12000
planner: Codex
created_at: 2026-09-20
---
# Task: Implement GitHub delivery profile

## Objective
Ship a provider-bounded GitHub delivery profile on Agora Core's reviewed Tool Pack contracts without adding a GitHub client or credentials.

## Business outcome
Teams can map governed AI-SDLC work to GitHub Issues, branches, pull requests, reviews, and checks while keeping Agora lifecycle state authoritative.

## Current state
Agora Core 0.8.2 provides reviewed `github-issues`, `github-pull-requests`, and `github-actions` CLI adapters. This repository has integration principles but no executable GitHub profile.

## Required inputs
- GitHub issues #4 and #27.
- `AGENTS.md` and `.agora/context/integration-contracts.md`.
- Agora Core 0.8.2 GitHub Tool Pack operation contracts.

## Allowed paths
- `.agora/execution/27/`
- `profiles/integrations/github/`
- `src/agora_ai_sdlc/github_delivery.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `samples/github-delivery/`
- `samples/README.md`
- `tests/fixtures/github-delivery/`
- `tests/test_github_delivery.py`
- `tests/test_github_delivery_sample.py`
- `docs/integrations/github.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Forbidden changes
- Agora Core or Studio code.
- Provider API or SDK clients.
- Core lifecycle, Tool Pack, or credential contracts.
- Unrelated policies, profiles, and refactors.

## Functional requirements
- Declare the Core adapters, operation mappings, evidence bindings, and least-privilege modes.
- Normalize issue, pull-request review, and Actions check facts into deterministic provider-neutral delivery facts.
- Require successful checks to match the expected immutable commit before gate evidence is accepted.
- Keep read-only access as the default; require explicit capability and confirmation for writes.
- Make repeated ingestion of an unchanged provider fact idempotent.
- Provide a credential-free executable sample and opt-in read-only live guidance.

## Non-functional requirements
- Offline and deterministic by default.
- No credentials or provider response bodies in durable diagnostics.
- External provider failures remain distinct from policy denials.
- Compatible with packaged Agora Core 0.8.2.

## Acceptance criteria
- [ ] Profile works read-only by default.
- [ ] Write operations require explicit capabilities and confirmation.
- [ ] Closed and reopened issue behavior is documented.
- [ ] PR, review, and check facts satisfy delivery only when bound to the expected commit/revision.

## Negative cases
- Stale check commit.
- Missing write capability.
- Missing write confirmation.
- Failed or pending check.
- Malformed or mismatched provider facts.

## Focused verification
- `uv run pytest tests/test_github_delivery.py tests/test_github_delivery_sample.py -q`
- `uv run ruff check src/agora_ai_sdlc/github_delivery.py tests/test_github_delivery.py tests/test_github_delivery_sample.py samples/github-delivery/run.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- Issue #14 is closed.
- Agora Core 0.8.2 reviewed GitHub Tool Pack contracts are installed and verified locally.

## Clarifications
None. The profile consumes existing Core adapter contracts and does not extend them.

## Completion evidence
- Normalized fixture tests, stale revision rejection, permission denial, idempotent ingest, executable offline sample, full repository verification, independent review, commit, and PR.
