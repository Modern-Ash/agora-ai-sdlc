---
issue: 98
epic: 92
title: Implement Method Pack 0.2.0 three-phase lifecycle as selectable default candidate
repository: Modern-Ash/agora-ai-sdlc
base_commit: 4014188dacb486bc97442d938d3e6d8ab576ff54
status: review
risk: high
context_size: large
budget:
  max_input_tokens: 42000
  max_output_tokens: 18000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Implement Method Pack 0.2.0 three-phase lifecycle

## Objective
Add a parallel, explicitly selectable AI-SDLC Method Pack 0.2.0 implementing the canonical lifecycle:
inception -> construction -> operations -> completed
while preserving the installed 0.1.0 pack for migration.

## Business outcome
Allow teams to validate and pilot the published three-phase lifecycle without breaking current 0.1.0 adopters. The new pack becomes the default candidate for future promotion, not the active packaged default in this ticket.

## Current state
- 0.1.0 lives at registry/methods/ai-sdlc and remains the current active/default sample pack.
- AWS-original conformance marks three-phase-lifecycle and minimal-roles PARTIAL.
- Later issues #99-#101 add first-class Level-N plans, adaptive pathway planning and executable Bolts.

## Required inputs
- issue #98 and parent epic #92
- AGENTS.md
- docs/reference/aws-ai-dlc-fidelity-plan.md
- current 0.1.0 Method Pack and lifecycle tests
- Agora Core Method Pack schema/optional roles support

## Allowed paths
- .agora/execution/98/**
- registry/method-versions/ai-sdlc/0.2.0/**
- src/agora_ai_sdlc/method_versions.py
- src/agora_ai_sdlc/scenario.py
- tests/test_method_versions.py
- tests/test_method_pack.py
- docs/method/migration-0.2.0.md
- docs/reference/aws-ai-dlc-fidelity-plan.md
- README.md

## Forbidden changes
- registry/methods/ai-sdlc/** (0.1.0 must remain byte-for-byte usable)
- existing profile method version pins
- existing samples' default behavior
- Agora Core
- conformance rule semantics outside what is needed to recognize the candidate pack

## Functional requirements
- Add Method Pack 0.2.0 with id ai-sdlc and version 0.2.0.
- States exactly [inception, construction, operations, completed].
- Required roles exactly [product-owner, developer].
- Optional role quality-reviewer.
- Gates: inception-approved, construction-verified, completion.
- Rework transitions construction->inception and operations->construction are ungated; Core durable transition history is the record.
- readiness-assessment and intent remain available flavor artifacts/capabilities, but are not lifecycle states.
- Provide explicit method_pack_path(version) for 0.1.0 and 0.2.0.
- Expose DEFAULT_METHOD_VERSION=0.1.0 and DEFAULT_CANDIDATE_VERSION=0.2.0.
- Lifecycle test harness can select method_version explicitly without changing current default.
- Both versions install and validate through Agora Core.
- Add migration documentation describing states, gates, roles, rework and non-breaking selection.
- Do not claim #99/#100/#101 features as completed.

## Acceptance criteria
- [x] 0.1.0 path resolves to current registry/methods/ai-sdlc.
- [x] 0.2.0 path resolves to versioned candidate pack.
- [x] invalid version fails closed.
- [x] 0.2.0 manifest has exact three-phase lifecycle plus completed terminal state.
- [x] 0.2.0 required roles are product-owner and developer; quality-reviewer is optional.
- [x] forward transitions use inception-approved, construction-verified and completion.
- [x] rework edges exist without gates.
- [x] both versions install/validate against current Core.
- [x] current Lifecycle()/samples still use 0.1.0 by default.
- [x] Lifecycle(method_version="0.2.0") starts in inception.
- [x] migration note documents explicit selection and breaking state/gate/role changes.
- [x] full repository verification passes.

## Focused verification
- uv run pytest -q tests/test_method_versions.py tests/test_method_pack.py tests/test_lifecycle.py
- uv run ruff check src/agora_ai_sdlc/method_versions.py src/agora_ai_sdlc/scenario.py tests/test_method_versions.py
- uv run ruff format --check src/agora_ai_sdlc/method_versions.py src/agora_ai_sdlc/scenario.py tests/test_method_versions.py

## Full verification
- uv run python scripts/verify_all.py

## Dependencies
#97 is complete in the stacked merge chain. Promotion PR #113 carries #97 to main; this issue is branched from that verified merge commit.

## Clarifications
- 0.2.0 is a selectable candidate only in this issue. Existing adoption profiles remain pinned to 0.1.0.
- First-class plan/Bolt semantics are explicitly deferred to #99/#101.

## Completion evidence
- TESTS.md with CI evidence
- RESULT.md
- independent REVIEW.md before merge
