---
issue: 41
epic: 8
title: Define assessment, pilot and adoption service packages
repository: Modern-Ash/agora-ai-sdlc
base_commit: b9a48f5
status: review
risk: medium
context_size: medium
planner: Codex
created_at: 2026-09-20
---
# Task: Define assessment, pilot and adoption service packages

## Objective
Publish bounded Professional Services packages for assessment, Starter pilot, Enterprise adoption, and legacy modernization, with every technical claim tied to the current flavor manifest or labeled consulting work.

## Allowed paths
- `.agora/execution/41/`
- `docs/commercial/`
- `tests/test_commercial_packages.py`
- `README.md`

## Forbidden changes
- Product runtime behavior, manifests, profiles, policies, Method Packs, or samples
- Pricing, customer-specific terms, legal/compliance guarantees, AWS endorsement, or marketplace submission
- Claims about Studio, SaaS, Control Plane, hosted registries, or managed provider credentials

## Functional requirements
- Define customer problem, prerequisites, activities, deliverables, exclusions, planning assumptions, and acceptance for every package.
- Label deliverables as implemented capability or consulting work.
- State customer and Modern Ash responsibilities explicitly.
- Separate Apache-2.0 software rights from paid delivery/support.
- Define measured baselines and customer-agreed success goals without guaranteed percentages.
- Make implemented-asset metadata machine-checkable against the current flavor manifest.

## Acceptance criteria
- [x] No unsupported feature is sold as available.
- [x] Customer and Modern Ash responsibilities are explicit.
- [x] Each package has entry and exit criteria.
- [x] Claims trace to implemented assets or are labeled consulting work/goals.

## Negative cases
- Unknown profile, policy, or Method Pack references fail documentation tests.
- Missing commercial sections or responsibility parties fail documentation tests.
- Prohibited certification, sponsorship, compliance, or productivity guarantees fail documentation tests.

## Focused verification
- `uv run pytest tests/test_commercial_packages.py -q`
- `uv run ruff check tests/test_commercial_packages.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- #12 product positioning, repository boundaries, and MVP scope are implemented on `main`.
- Implemented release assets are declared by `src/agora_ai_sdlc/flavor/flavor.yaml`.

## Clarifications
The Regulated profile is referenced only as an optional readiness assessment within Enterprise adoption. A separate regulated service package is not among this issue's expected files and is not introduced here.

## Completion evidence
Documentation and verification complete; independent review pending.
