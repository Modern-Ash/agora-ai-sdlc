---
issue: 28
epic: 4
title: Implement generic CI/CD evidence profile
repository: Modern-Ash/agora-ai-sdlc
base_commit: 49e878d
status: review
risk: medium
context_size: medium
budget:
  max_input_tokens: 30000
  max_output_tokens: 12000
planner: Codex
created_at: 2026-09-20
---
# Task: Implement generic CI/CD evidence profile

## Objective
Ship a provider-neutral, offline-first contract that turns bounded CI/CD observations into current-revision Agora evidence without executing CI.

## Business outcome
Teams can use GitHub Actions, GitLab CI, Jenkins, or a reviewed generic Core adapter while applying identical build, test, security, deployment, and smoke-test evidence rules.

## Current state
Agora Core 0.8.2 owns CI/CD Tool Pack operations and evidence persistence. The AI-SDLC Method Pack already requires `test-suite`, `deployment`, and `security-scan` evidence, but this flavor has no neutral normalization or freshness profile.

## Required inputs
- GitHub issues #4, #18, and #28.
- `AGENTS.md` and `.agora/context/integration-contracts.md`.
- Agora Core 0.8.2 `ci-cd` Tool Pack and evidence contracts.
- Existing late-gate and GitHub profile behavior.

## Allowed paths
- `.agora/execution/28/`
- `profiles/integrations/ci/`
- `src/agora_ai_sdlc/ci_evidence.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `samples/ci-evidence/`
- `samples/README.md`
- `tests/fixtures/ci-evidence/`
- `tests/test_ci_evidence.py`
- `tests/test_ci_evidence_sample.py`
- `docs/integrations/ci.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Forbidden changes
- Agora Core or Studio code.
- Provider SDK/API clients or CI executors.
- Existing Method Pack gates or lifecycle semantics.
- Credentials, logs, environment dumps, or provider response bodies.
- Unrelated refactors.

## Functional requirements
- Normalize build, unit, integration, security, quality, deployment, and smoke-test facts.
- Bind each fact to provider, repository, full commit, environment, run ID, and bounded evidence URL.
- Define exact success, failure, cancelled, and unknown statuses.
- Produce Core-compatible `test-suite`, `security-scan`, and `deployment` evidence bundles only from complete successful current facts.
- Make unchanged duplicate run/category ingestion idempotent and conflicting duplicates fail closed.
- Include equivalent GitHub Actions, GitLab CI, and Jenkins fixtures/examples without selecting a canonical provider.
- Provide an executable credential-free lifecycle sample.

## Non-functional requirements
- Deterministic and offline by default.
- No secret-bearing URL components or unbounded output fields.
- Provider execution failure remains distinct from policy mismatch.
- Compatible with packaged Agora Core 0.8.2.

## Acceptance criteria
- [ ] Only successful current-revision results satisfy positive gates.
- [ ] Cancelled and unknown never count as success.
- [ ] Evidence references are bounded and cannot embed credentials/query secrets.
- [ ] Duplicate run ingestion is idempotent.

## Negative cases
- Failure, cancelled, and unknown status.
- Stale commit and environment/repository mismatch.
- Missing category in a gate bundle.
- Duplicate identity with changed payload.
- URL credentials, query, fragment, unsupported scheme, or excessive length/count.

## Focused verification
- `uv run pytest tests/test_ci_evidence.py tests/test_ci_evidence_sample.py -q`
- `uv run ruff check src/agora_ai_sdlc/ci_evidence.py tests/test_ci_evidence.py tests/test_ci_evidence_sample.py samples/ci-evidence/run.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- Issue #18 remains open administratively, but its required late gates, evidence types, tests, and successful completion scenario are present on `main`; no missing Core capability blocks this issue.

## Clarifications
None. The profile consumes Core evidence and Tool Pack contracts without changing either schema.

## Completion evidence
Status matrix, freshness/environment tests, bounded-reference tests, duplicate fixture, three provider examples, executable sample, full verification, commit, PR, CI, and independent PR review request.
