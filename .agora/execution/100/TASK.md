---
issue: 100
epic: 92
title: Implement adaptive pathway planning and conditional stage execution
repository: Modern-Ash/agora-ai-sdlc
base_commit: 88c5000a6a6d76b7fe830464d3c9582baa25ee65
status: review
risk: high
context_size: large
budget:
  max_input_tokens: 42000
  max_output_tokens: 18000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Implement adaptive pathway planning and conditional stage execution

## Objective
Add deterministic adaptive pathway policy over first-class approved plans so one three-phase Method Pack lifecycle can support trivial changes, new products, brown-field work, refactors, scaling and regulated work without adding pathway-specific state machines.

## Business outcome
Allow AI to propose what to execute, skip or deepen while Agora remains the policy authority: governance obligations remain non-skippable, depth/adoption profiles constrain optionality, and accountable humans approve the exact plan revision before execution.

## Current state
Method Pack 0.2.0 is on main as the selectable three-phase candidate. Issue #99 provides durable Level 1 / Level-N plans with execute/skip decisions and exact-revision approval. This issue adds policy validation and pathway semantics; it does not execute code or Bolts.

## Required inputs
- issue #100 and parent epic #92
- AGENTS.md
- src/agora_ai_sdlc/plans.py
- src/agora_ai_sdlc/depth_profiles.py
- adoption profiles under profiles/
- Method Pack 0.2.0 migration note and gates
- issue #99 plan fixtures/tests

## Allowed paths
- .agora/execution/100/**
- src/agora_ai_sdlc/adaptive_planning.py
- src/agora_ai_sdlc/plans.py
- tests/test_adaptive_planning.py
- tests/fixtures/pathways/**
- docs/method/adaptive-planning.md
- docs/method/planning.md
- profiles/pathways/**
- profiles/README.md
- tests/test_cli.py
- src/agora_ai_sdlc/cli.py
- src/agora_ai_sdlc/conformance/self_test.py
- tests/conformance/test_self_test.py

## Forbidden changes
- Agora Core
- Method Pack lifecycle/gates/roles
- generic artifact schema version
- compatibility scoring/rule semantics
- Bolt execution semantics (#101)
- provider/model/cloud SDKs
- hidden heuristics that are not represented as checked-in policy

## Functional requirements
- Define a versioned pathway policy contract.
- Support pathway ids: trivial-change, new-product, brownfield, refactor, scaling, regulated-change.
- A pathway declares recommended depth, mandatory steps, optional steps and forbidden skips.
- Plan decisions remain execute|skip; skipped steps require non-empty rationale.
- Policy validator rejects unknown plan step ids for the selected pathway.
- Policy validator rejects skip of mandatory or forbidden-skip steps.
- Effective depth is the stricter of pathway minimum and active/adoption profile depth.
- Depth constraints may promote optional steps to mandatory but may never demote protected obligations.
- Regulated profile/depth always forces governed review/security/operations obligations.
- Plan must be approved at its current revision before pathway execution is considered allowed.
- Human can modify/reject by producing a new/revised plan; stale approval remains blocked by #99 semantics.
- Same Method Pack 0.2.0 lifecycle is used for all pathways; no pathway-specific state machine.
- Expose read-only CLI validation: `agora-ai-sdlc plan-validate PATH --pathway ID [--profile ID|--depth ID]`.
- All validation is offline and deterministic.

## Initial pathway step vocabulary
Use a closed method-step vocabulary aligned to existing artifacts/gates:
- clarify-intent
- elaborate-stories
- define-nfrs
- assess-risks
- measurement-criteria
- decompose-units
- domain-design
- logical-design
- threat-model
- implementation
- unit-tests
- integration-tests
- security-tests
- performance-tests
- deployment-unit
- deployment
- observability
- rollback-readiness
- brownfield-static-model
- brownfield-dynamic-model

## Acceptance criteria
- [x] same lifecycle supports all six pathways.
- [x] trivial change fixture can skip non-mandatory design activities under minimal/standard depth.
- [x] new product fixture executes full inception/construction baseline.
- [x] brownfield fixture requires semantic elevation before construction.
- [x] regulated fixture cannot skip security/review/operations obligations.
- [x] active profile/depth can only increase obligations above pathway minimum.
- [x] invalid attempt to skip mandatory policy fails closed with stable code.
- [x] stale/unapproved plan cannot be execution-authorized.
- [x] CLI validates approved plans and returns non-zero for policy violations.
- [x] golden fixtures are deterministic and provider-neutral.
- [x] full repository verification passes.

## Focused verification
- uv run pytest -q tests/test_adaptive_planning.py tests/test_plans.py tests/test_cli.py
- uv run ruff check src/agora_ai_sdlc/adaptive_planning.py src/agora_ai_sdlc/cli.py tests/test_adaptive_planning.py
- uv run ruff format --check src/agora_ai_sdlc/adaptive_planning.py src/agora_ai_sdlc/cli.py tests/test_adaptive_planning.py

## Full verification
- uv run python scripts/verify_all.py

## Dependencies
#99 / PR #116 is the direct dependency and this branch is stacked on its current head. Do not merge #100 before #99.

## Clarifications
None required. This issue validates adaptive pathway policy and execution authorization only. Actual step execution and executable Bolt scheduling remain #101.

## Completion evidence
- TESTS.md
- RESULT.md
- independent REVIEW.md before merge
