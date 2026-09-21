---
issue: 105
epic: 93
title: Implement cross-repository impact analysis contract
repository: Modern-Ash/agora-ai-sdlc
base_commit: 3b8290f155b008772c129d918da75b4db461136f
status: review
risk: medium
context_size: medium
budget:
  max_input_tokens: 36000
  max_output_tokens: 16000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Implement cross-repository impact analysis contract

## Objective
Represent and validate provider-neutral impact analysis across repositories, components and contracts before implementation.

## Business outcome
Give enterprise delivery a durable, approved impact-analysis artifact that makes cross-repository blast radius, ownership, dependencies, unknowns and expected changes explicit before implementation begins.

## Current state
Agora AI-SDLC has first-class Units, Plans, Bolt Plans, enterprise review policies and generic artifact traceability, but no impact-analysis artifact or cross-repository contract.

## Allowed paths
- .agora/execution/105/**
- templates/impact-analysis.md
- templates/README.md
- src/agora_ai_sdlc/artifacts.py
- src/agora_ai_sdlc/impact_analysis.py
- tests/test_templates.py
- tests/test_impact_analysis.py
- tests/fixtures/impact-analysis/**
- samples/cross-repo-impact/**
- samples/README.md
- docs/method/artifacts.md
- docs/method/impact-analysis.md
- profiles/reviews/enterprise.yaml
- profiles/reviews/regulated.yaml
- docs/policies/enterprise-review-gates.md

## Forbidden changes
- Agora Core
- Method Pack lifecycle/transitions/roles
- provider-specific repository identifiers
- GitHub/GitLab APIs
- hidden dependency discovery via network
- automatic mutation of external repositories

## Functional requirements
- Register impact-analysis as artifact kind with IMA prefix.
- Use existing artifact/v1 envelope and generic traceability.
- Require Unit scope and allow Plan/Bolt Plan references.
- Require at least two affected repositories for cross-repository analysis.
- Repository ids are provider-neutral slugs; optional repository refs are opaque URI-like strings and must not require a provider.
- Represent affected components/modules per repository.
- Represent APIs/events/schemas as contracts with owner repository and expected change.
- Represent dependencies with source, target, direction and known|unknown status.
- Unknown dependencies must include a reason and remain first-class in the artifact.
- Record expected changes, owners, reviewers, confidence and unknowns.
- Exact-revision approval semantics: pending|approved|rejected, approved-by, approved-revision.
- Approved analysis requires reviewer distinct from at least one declared owner.
- Unit/Plan/Bolt Plan references must be trace-bound.
- Provide deterministic summary and affected-repository query API.
- Enterprise/regulated review policy can require approved-impact-analysis evidence before architecture review passes.
- Multi-repo sample is offline and provider-neutral.

## Acceptance criteria
- [x] valid multi-repo artifact parses.
- [x] repository ids/components/contracts/dependencies validate.
- [x] unknown dependencies remain explicit and require rationale.
- [x] approval is exact-revision and stale approval fails closed.
- [x] owner/reviewer separation enforced.
- [x] Unit/Plan/Bolt Plan trace references validated.
- [x] sample covers at least three repositories and two contract types.
- [x] enterprise architecture review requires approved-impact-analysis evidence.
- [x] generic traceability accepts impact-analysis.
- [x] full repository verification passes.

## Focused verification
- uv run pytest -q tests/test_impact_analysis.py tests/test_templates.py tests/test_enterprise_reviews.py
- uv run ruff check src/agora_ai_sdlc/impact_analysis.py src/agora_ai_sdlc/artifacts.py tests/test_impact_analysis.py
- uv run ruff format --check src/agora_ai_sdlc/impact_analysis.py src/agora_ai_sdlc/artifacts.py tests/test_impact_analysis.py

## Full verification
- uv run python scripts/verify_all.py

## Dependencies
#104 is merged to main. No Core change is required.

## Scope boundary
This issue records and validates declared impact. Automated dependency discovery across repositories is not part of this ticket and no provider API is required.

## Completion evidence
- TESTS.md
- RESULT.md
- independent REVIEW.md before merge
