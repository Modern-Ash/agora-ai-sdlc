---
issue: 104
epic: 93
title: Add enterprise review-gate and policy bundle
repository: Modern-Ash/agora-ai-sdlc
base_commit: eeab625daf9d36fd91e495c0abce6cbc0e251c4c
status: implementing
risk: medium
context_size: medium
budget:
  max_input_tokens: 32000
  max_output_tokens: 14000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Add enterprise review-gate and policy bundle

## Objective
Provide configurable, vendor-neutral enterprise review gates for business, architecture, security/compliance, quality, and operational readiness without creating a second lifecycle engine.

## Business outcome
Allow the LG-enterprise operating model to express mandatory review controls using existing Agora approval/evidence primitives and existing independent-review policies while preserving Core as lifecycle authority.

## Current state
The five-stage LG-enterprise presentation is merged. Agora already has artifact-scoped independent review, depth/adoption profiles, and Core approval/evidence primitives, but no reusable enterprise review-gate bundle.

## Allowed paths
- .agora/execution/104/**
- profiles/reviews/**
- src/agora_ai_sdlc/enterprise_reviews.py
- src/agora_ai_sdlc/conformance/self_test.py
- tests/test_enterprise_reviews.py
- docs/policies/enterprise-review-gates.md
- profiles/README.md

## Forbidden changes
- Agora Core
- Method Pack lifecycle, transitions, gate semantics or roles
- LG presentation profile mappings
- provider-specific reviewer integrations
- remote/network calls
- changes that turn review policy into a parallel lifecycle authority

## Functional requirements
- Add versioned review-policy profiles for starter, enterprise and regulated adoption.
- Five review ids: business-review, architecture-review, security-compliance-review, quality-review, operational-readiness-review.
- Each review declares mandatory/optional, required approval roles, required evidence types, and independent-review profiles.
- Starter may keep non-critical architecture/security reviews optional.
- Enterprise requires all five reviews.
- Regulated requires all five plus regulated independent-review for sensitive reviews and governance-owner participation where configured.
- Evaluation consumes only approval/evidence facts and independent-review decisions; no provider tooling.
- Missing mandatory review evidence/approval blocks progress.
- Optional missing reviews do not block.
- Independent-review requirements use the existing independent_review profile vocabulary.
- Unknown profiles/reviews/evidence fail deterministically.
- Packaged self-test validates all review policy files.

## Acceptance criteria
- [ ] standard/starter fixture passes with non-critical reviews optional.
- [ ] enterprise fixture passes with all mandatory review controls present.
- [ ] regulated fixture passes with regulated separation/human-final review decisions.
- [ ] missing mandatory review blocks with stable code/result.
- [ ] optional missing review does not block.
- [ ] independent-review policy requirement is enforced.
- [ ] all policy assets validate offline.
- [ ] full repository verification passes.

## Focused verification
- uv run pytest -q tests/test_enterprise_reviews.py
- uv run ruff check src/agora_ai_sdlc/enterprise_reviews.py tests/test_enterprise_reviews.py
- uv run ruff format --check src/agora_ai_sdlc/enterprise_reviews.py tests/test_enterprise_reviews.py

## Full verification
- uv run python scripts/verify_all.py

## Dependencies
#103 is merged to main. No Core change is required.

## Scope boundary
This issue evaluates review readiness before callers record/advance through Core lifecycle gates. Core remains authoritative; the bundle never transitions work or writes approvals itself.

## Completion evidence
- TESTS.md
- RESULT.md
- independent REVIEW.md before merge
