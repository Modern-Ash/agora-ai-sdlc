---
issue: 30
epic: 4
title: Specify GitLab and Jira follow-on profiles
repository: Modern-Ash/agora-ai-sdlc
base_commit: 825de8d
status: verified
risk: high
context_size: medium
budget:
  max_input_tokens: 30000
  max_output_tokens: 12000
planner: Codex
created_at: 2026-09-20
---
# Task: Specify GitLab and Jira follow-on profiles

## Objective
Map GitLab issues, merge requests and pipelines plus Jira work items and transitions into the provider-neutral delivery semantics established by the GitHub profile.

## Business outcome
Teams can replace GitHub work-management and delivery systems without changing Agora lifecycle meaning, evidence semantics, or write safeguards.

## Current state
The GitHub profile establishes neutral `issue.*`, `review.*`, and `ci.*` capabilities, immutable delivery observations, read-only defaults, and explicit write grants. Agora Core 0.8.2 supplies reviewed CLI adapters for GitLab issues, merge requests and CI plus Jira Cloud work items.

## Required inputs
- GitHub issues #4, #27, and #30.
- `AGENTS.md`, integration contracts, GitHub profile, tests, and documentation.
- Installed Agora Core 0.8.2 GitLab and Jira Tool Pack contracts.

## Allowed paths
- `.agora/execution/30/`
- `profiles/integrations/gitlab/`
- `profiles/integrations/jira/`
- `src/agora_ai_sdlc/follow_on_delivery.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `samples/gitlab-delivery/`
- `samples/jira-work-items/`
- `samples/README.md`
- `tests/test_follow_on_delivery.py`
- `tests/test_follow_on_delivery_samples.py`
- `docs/integrations/gitlab-jira.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Forbidden changes
- Agora Core, Studio, Method Pack, or lifecycle code.
- Provider SDK/API clients or live-account access.
- Credentials, provider responses containing secrets, or unbounded raw payloads.
- Provider names in Method Pack behavior.
- Implicit writes, merge/approval emulation, or unsupported operation fallbacks.
- Unrelated refactors.

## Functional requirements
- Declare GitLab and Jira profiles using the same neutral capabilities as the GitHub profile.
- Normalize GitLab issues/MRs/pipelines and Jira work items into bounded immutable observations.
- Demonstrate equivalent normalized work-item outcomes across GitLab and Jira fixtures.
- Preserve Agora as lifecycle authority; external transitions describe external state only.
- Keep each external system authoritative for its own work-item/review/pipeline facts.
- Reconcile by appending changed observations and treating identical retries as no-ops.
- Default to read-only; require the declared mode, explicit capability grant, and confirmation for every write.
- Reject unsupported operations with stable provider-specific error codes.

## Non-functional requirements
- Deterministic, credential-free, and offline.
- Validate profile operations against installed Core Tool Pack contracts.
- Keep provider fields inside fixtures and translation functions.
- Reject unsafe URLs, stale revisions, incomplete facts, and malformed states.

## Acceptance criteria
- [ ] No Method Pack file branches on provider name.
- [ ] Provider-specific fields remain inside adapter/profile mapping.
- [ ] Contract fixtures demonstrate equivalent normalized outcomes.
- [ ] Unsupported operation fails clearly.

## Negative cases
- Unknown operation or permission mode.
- Write without mode, capability grant, or confirmation.
- GitLab operation absent from Core adapter contract.
- Jira operation outside work-management support.
- Missing required fact, unsafe/mismatched URL, stale pipeline revision, or failed pipeline.

## Focused verification
- `uv run pytest tests/test_follow_on_delivery.py tests/test_follow_on_delivery_samples.py -q`
- `uv run ruff check src/agora_ai_sdlc/follow_on_delivery.py tests/test_follow_on_delivery.py tests/test_follow_on_delivery_samples.py samples/gitlab-delivery/run.py samples/jira-work-items/run.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- Issue #27 is implemented and merged.
- Agora Core 0.8.2 contains the referenced GitLab and Jira CLI adapters.

## Clarifications
None. Jira has no code-review or CI contract, while GitLab Core adapters deliberately omit issue creation, MR approval/merge, and pipeline trigger; the profiles must expose those absences rather than emulate them.

## Completion evidence
Profile contract tests, fixture parity, permission and external-failure tests, two executable samples, full verification, commit, PR, CI, and independent PR review request.
