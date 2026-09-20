---
issue: 29
epic: 4
title: Define security-finding normalization profile
repository: Modern-Ash/agora-ai-sdlc
base_commit: 4ae70d5
status: review
risk: high
context_size: medium
budget:
  max_input_tokens: 30000
  max_output_tokens: 12000
planner: Codex
created_at: 2026-09-20
---
# Task: Define security-finding normalization profile

## Objective
Normalize provider-neutral security findings, decisions, and depth-profile blocking into durable Agora Core findings and gate evidence.

## Business outcome
Teams can combine SAST, dependency, secret, container, and IaC scanners without changing severity semantics or losing accountable risk decisions.

## Current state
Agora Core 0.8.2 supplies read-only `security-scanning` operations, structured review findings (`open`, `resolved`, `waived`), and `security-scan` evidence. The flavor has depth profiles but no finding schema, thresholds, or decision authority policy.

## Required inputs
- GitHub issues #4, #18, and #29.
- `AGENTS.md`, integration contracts, late gates, depth profiles, and role authority.
- Agora Core 0.8.2 security Tool Pack, review finding, and evidence contracts.

## Allowed paths
- `.agora/execution/29/`
- `profiles/integrations/security/`
- `src/agora_ai_sdlc/security_findings.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `samples/security-findings/`
- `samples/README.md`
- `tests/test_security_findings.py`
- `tests/test_security_findings_sample.py`
- `docs/integrations/security.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Forbidden changes
- Agora Core or Studio code.
- Scanner SDK/API clients or active scanning.
- Existing lifecycle gates, depth inheritance, or Core finding schemas.
- Raw reports, secret values, credentials, or provider logs.
- Reuse of independent-review waivers as security risk acceptance.
- Unrelated refactors.

## Functional requirements
- Normalize SAST, dependency, secret, container, and IaC findings with severity, rule, location, scanner identity/reference, status, and decision.
- Define monotonic blocking thresholds for minimal, standard, comprehensive, and regulated depths.
- Treat unknown severity as blocking for every profile.
- Preserve original finding fields when adding resolved, accepted-risk, or false-positive decisions.
- Require an accountable actor, authorized role, reason, and bounded evidence reference for every decision.
- Restrict accepted risk to a human governance owner; restrict resolved/false-positive to a security reviewer.
- Map normalized findings and decisions to Core structured review records and emit `security-scan` success only when no blocking finding remains.
- Keep raw scanner reports as bounded external references.

## Non-functional requirements
- Deterministic and offline.
- Scanner names never affect thresholds or decisions.
- Fail closed on unknown severity, invalid status, incomplete/unauthorized decisions, or unsafe references.
- Compatible with packaged Agora Core 0.8.2.

## Acceptance criteria
- [ ] Open findings at or above the active-profile threshold block `security-scan` success.
- [ ] Scanner names do not alter semantic behavior.
- [ ] Waiver/risk acceptance never deletes or mutates the original finding identity/content.
- [ ] Raw reports remain external references unless separately imported as Core artifacts.

## Negative cases
- Threshold boundary for every profile/severity.
- Unknown severity.
- Unauthorized or AI governance waiver.
- Missing actor, reason, role, or decision evidence.
- Unsafe scanner report/decision reference.
- Unsupported category, status, or decision.

## Focused verification
- `uv run pytest tests/test_security_findings.py tests/test_security_findings_sample.py -q`
- `uv run ruff check src/agora_ai_sdlc/security_findings.py tests/test_security_findings.py tests/test_security_findings_sample.py samples/security-findings/run.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- Issue #18 remains open administratively, but its completion gate and `security-scan` evidence requirement are implemented and tested on `main`.
- Core structured review finding APIs are present in installed Agora Core 0.8.2.

## Clarifications
None. Rich flavor decisions map `resolved` to Core `resolved` and accepted-risk/false-positive to Core `waived`; the flavor record remains the semantic authority for the decision kind. Core 0.8.2 cannot add non-required security/governance seats to an existing base swarm, so the flavor enforces decision authority and the assigned quality-reviewer persists Core evidence.

## Completion evidence
Severity matrix, authority tests, unknown fail-closed test, scanner invariance, Core mapping, executable sample, full verification, commit, PR, CI, and independent PR review request.
