---
issue: 99
epic: 92
title: Make Level 1 Plan and recursive Level-N plans first-class artifacts
repository: Modern-Ash/agora-ai-sdlc
base_commit: b9769ccd981e58dae36f3f5e9aa90e1a36a70fe5
status: implementing
risk: high
context_size: large
budget:
  max_input_tokens: 42000
  max_output_tokens: 18000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Make Level 1 Plan and recursive Level-N plans first-class artifacts

## Objective
Represent AI-proposed plans as durable, traceable, human-approved flavor artifacts with deterministic validation and recursive parent/child semantics.

## Business outcome
Make the Level 1 -> Level N planning model executable as a portable Agora AI-SDLC contract, without coupling planning to an LLM/provider or teaching Agora Core method-specific plan semantics.

## Current state
Method Pack 0.2.0 exists as a selectable candidate. AWS-original fidelity currently marks level-1-plan PARTIAL and recursive-planning FAIL because no first-class plan template/validator exists.

## Required inputs
- issue #99 and parent epic #92
- AGENTS.md
- docs/reference/aws-ai-dlc-fidelity-plan.md
- src/agora_ai_sdlc/artifacts.py
- generic artifact traceability conventions
- AWS fidelity rules and generated Marketplace matrix

## Allowed paths
- .agora/execution/99/**
- templates/plan.md
- templates/README.md
- src/agora_ai_sdlc/artifacts.py
- src/agora_ai_sdlc/plans.py
- tests/test_templates.py
- tests/test_plans.py
- tests/fixtures/plans/**
- tests/fixtures/conformance/aws-original/current.yaml
- docs/method/artifacts.md
- docs/method/planning.md
- docs/commercial/marketplace/compatibility-evidence.md

## Forbidden changes
- Agora Core
- Method Pack lifecycle/gates/roles
- compatibility rule semantics
- existing artifact schema version
- provider/model/cloud dependencies
- #100 adaptive pathway policy
- #101 executable Bolt model

## Functional requirements
- Register plan as artifact kind with PLN prefix.
- Add plan template using existing artifact/v1 envelope plus plan-specific front matter.
- Plan fields: level, parent-plan, intent, unit, steps, proposed-by, approval-state, approved-by, approved-revision.
- Ordered steps contain id, decision execute|skip, rationale, dependencies, required-artifacts, produced-artifacts.
- Level 1 has no parent; level > 1 requires parent-plan.
- Child plan must trace to its parent plan and parent level must be exactly child level - 1.
- Intent scope required; Unit scope optional.
- Step ids unique; dependencies reference known earlier steps only.
- Skip decisions require rationale; execute decisions also retain rationale.
- Approval states: pending, approved, rejected.
- Approved plans require accountable approved-by and approved-revision equal to current artifact revision.
- Pending/rejected plans are not executable.
- Changed approved plan revision is stale until re-approved at the new revision.
- Plan graph rejects missing parents, wrong levels, scope mismatch, duplicate ids and cycles/invalid parent chains.
- All validation is offline/deterministic.

## Acceptance criteria
- [ ] parser/validator and template exist.
- [ ] Level 1 approval enforcement exists.
- [ ] Level N parent/trace/level validation exists.
- [ ] stale approval after revision change fails closed.
- [ ] ordered step dependency validation exists.
- [ ] golden Level 1 + Level 2 fixtures validate.
- [ ] invalid graph/approval fixtures or mutations fail with stable codes.
- [ ] generic artifact traceability accepts plan artifacts without weakening existing rules.
- [ ] AWS fidelity golden updates level-1-plan and recursive-planning to PASS.
- [ ] generated Marketplace compatibility evidence is updated deterministically.
- [ ] full repository verification passes.

## Focused verification
- uv run pytest -q tests/test_plans.py tests/test_templates.py tests/conformance/test_aws_original_rules.py tests/test_marketplace_evidence.py
- uv run ruff check src/agora_ai_sdlc/plans.py src/agora_ai_sdlc/artifacts.py tests/test_plans.py
- uv run ruff format --check src/agora_ai_sdlc/plans.py src/agora_ai_sdlc/artifacts.py tests/test_plans.py
- uv run python scripts/check_marketplace_evidence.py

## Full verification
- uv run python scripts/verify_all.py

## Dependencies
#98 implementation is required. Promotion PR #115 carries #98 into main; this issue is stacked on that verified merge commit.

## Clarifications
Plan approval is enforced by the flavor contract in this issue. Integration of plan selection into adaptive execution is #100. This ticket does not add provider-specific planning or automatically execute steps.

## Completion evidence
- TESTS.md
- RESULT.md
- independent REVIEW.md before merge
