---
issue: 38
epic: 7
title: Execute an existing-codebase multi-LLM pilot
repository: Modern-Ash/agora-ai-sdlc
base_commit: 764a014
status: review
risk: high
context_size: large
planner: Codex
created_at: 2026-09-20
---
# Task: Execute an existing-codebase multi-LLM pilot

## Objective
Ship a credential-free, repeatable pilot over a maintained existing codebase that exercises definition, implementation, independent review, correction, CI evidence, acceptance, and provider replacement through real Agora Core sessions.

## Allowed paths
- `.agora/execution/38/`
- `samples/existing-codebase-pilot/`
- `samples/README.md`
- `docs/pilots/existing-codebase.md`
- `tests/test_existing_codebase_pilot.py`

## Forbidden changes
- Agora Core contracts or lifecycle states
- Method Pack, policy, integration-profile, or provider-adapter behavior
- Live credentials, provider SDKs, network calls, or production claims

## Functional requirements
- Start from a small maintained code fixture and an explicit change request.
- Use adapter-shaped fake runners in default CI while launching real Core sessions.
- Record producer/reviewer runtime and provider provenance for exact revisions.
- Reject the first review, block a lifecycle gate, correct the implementation, and approve the corrected revision independently.
- Replace the producer provider without changing the installed Method Pack.
- Record normalized current-commit CI evidence before acceptance.
- Publish an optional live two-provider procedure with no credentials in repository state.
- Separate measured pilot facts from expectations requiring live or production observation.

## Acceptance criteria
- [x] Offline pilot completes deterministically from source and the installed package.
- [x] Producer provider replacement leaves the Method Pack digest unchanged.
- [x] Producer and reviewer provenance is visible and satisfies distinct actor/provider policy.
- [x] A review and the construction-to-operations gate reject before correction.
- [x] Baseline and result metrics clearly distinguish measured facts from expectations.

## Negative cases
- First implementation omits required invalid-quantity behavior.
- A non-approving review cannot satisfy independent-review policy.
- Operations transition is attempted before verification evidence and approval.

## Focused verification
- `uv run pytest tests/test_existing_codebase_pilot.py tests/conformance/runtimes/test_matrix.py -q`
- `uv run ruff check samples/existing-codebase-pilot/run.py samples/existing-codebase-pilot/fake_runner.py tests/test_existing_codebase_pilot.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- #26 multi-runtime conformance matrix
- #27 GitHub delivery profile
- #31 Starter profile
- Agora Core 0.8.2 session, runtime, evidence, and lifecycle APIs

## Clarifications
Python standard-library code is the issue's permitted equivalent to Java/Spring Boot and keeps the executable pilot deterministic on every supported Python version.

## Completion evidence
Implementation and verification complete; independent review pending.
