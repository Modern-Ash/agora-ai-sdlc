---
issue: 31
epic: 4
title: Define observability and operational-evidence profile
repository: Modern-Ash/agora-ai-sdlc
base_commit: ae10726
status: review
risk: high
context_size: medium
budget:
  max_input_tokens: 30000
  max_output_tokens: 12000
planner: Codex
created_at: 2026-09-20
---
# Task: Define observability and operational-evidence profile

## Objective
Normalize portable metric, deployment, and smoke observations and evaluate reviewed Agora Core control bands without granting production mutation authority.

## Business outcome
Operators can use replaceable monitoring systems to prove release readiness and open governed follow-up work from severe signals while Agora remains lifecycle authority.

## Current state
Issue #18 requires current deployment evidence at completion. Issue #28 can produce it from CI, while Agora Core 0.8.2 supplies provider-neutral observability operations, durable evidence, deterministic control bands, and governed Intent creation. No operational metric profile exists.

## Required inputs
- GitHub issues #4, #18, and #31.
- `AGENTS.md`, integration contracts, completion gates, and generic CI evidence patterns.
- Installed Agora Core 0.8.2 observability and control-band contracts.

## Allowed paths
- `.agora/execution/31/`
- `profiles/integrations/observability/`
- `src/agora_ai_sdlc/operational_evidence.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `samples/operational-evidence/`
- `samples/README.md`
- `tests/test_operational_evidence.py`
- `tests/test_operational_evidence_sample.py`
- `docs/integrations/observability.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Forbidden changes
- Agora Core, Studio, Method Pack, gate, or lifecycle code.
- Provider SDK/API clients, live-account access, credentials, or raw logs.
- Provider adapters not present in Core.
- Automatic incident, deployment, rollback, or production mutation.
- Unrelated refactors.

## Functional requirements
- Normalize name, value, unit, window, environment, source, and timestamp.
- Demonstrate equivalent CloudWatch, Azure Monitor, GCP Monitoring, Prometheus, and OpenTelemetry mappings.
- Bind successful deployment and smoke observations to the expected release, revision, and environment.
- Reject stale, future, wrong-environment, wrong-release, failed, malformed, and unsafe observations.
- Produce Core deployment evidence only from a complete current readiness bundle.
- Evaluate metrics using Core `AddControlBandInput` and `EvaluateControlBandInput`.
- Let Core propose governed Intent for a severe result; never invoke operational writes.

## Acceptance criteria
- [x] Examples remain optional adapters, not dependencies.
- [x] Stale or wrong-environment signals cannot satisfy readiness.
- [x] Severe control-band result proposes governed intent, never mutates production.
- [x] Missing unit/window produces validation error.

## Focused verification
- `uv run pytest tests/test_operational_evidence.py tests/test_operational_evidence_sample.py -q`
- `uv run ruff check src/agora_ai_sdlc/operational_evidence.py tests/test_operational_evidence.py tests/test_operational_evidence_sample.py samples/operational-evidence/run.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- Issue #18 and Agora Core control bands are implemented.
- Issue #28 provides the established deployment-evidence shape.

## Clarifications
None. Provider examples are fixture translators over Core's neutral `observability` Tool Pack contract; they are not executable provider adapters.

## Completion evidence
Profile contract tests, five-provider fixture parity, readiness negatives, real Core control-band/Intent test, executable sample, full verification, PR, CI, and independent review.
