---
issue: 97
epic: 91
title: Publish compatibility evidence matrix for Marketplace claims
repository: Modern-Ash/agora-ai-sdlc
base_commit: 398ec6b59086a5c3e3cbbb13d24b3fabbea76648
status: review
risk: medium
context_size: medium
budget:
  max_input_tokens: 32000
  max_output_tokens: 14000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Publish compatibility evidence matrix for Marketplace claims

## Objective
Generate a deterministic, evidence-backed compatibility matrix for Marketplace/release documentation from the checked-in compatibility contracts and conformance rule providers.

## Business outcome
Prevent marketing/documentation drift from executable conformance evidence. Buyer-facing compatibility language must remain bounded by current repository evidence and must never imply AWS/LG endorsement, certification, or private implementation knowledge.

## Current state
AWS-original has executable repository-derived fidelity rules. LG-enterprise has a public compatibility target profile but no implementation rule provider yet. Agora additive governance is available from the AWS rule provider and must be shown separately from base-method fidelity.

## Required inputs
- Issue #97 and epic #91.
- #95 generic conformance engine.
- #96 AWS-original rule provider.
- aws-original and lg-enterprise compatibility profiles.
- Marketplace listing and claim substantiation workspace.

## Allowed paths
- .agora/execution/97/**
- src/agora_ai_sdlc/marketplace_evidence.py
- scripts/check_marketplace_evidence.py
- scripts/verify_all.py
- tests/test_marketplace_evidence.py
- tests/test_marketplace_content.py
- docs/commercial/marketplace/compatibility-evidence.md
- docs/commercial/marketplace/README.md
- docs/commercial/marketplace/listing.md
- docs/commercial/marketplace/claim-substantiation.md

## Forbidden changes
- Agora Core.
- compatibility profile/rule semantics.
- Method Pack behavior.
- seller account/private-offer data.
- wording implying AWS/LG sponsorship, endorsement, certification or private/proprietary compatibility.

## Functional requirements
- Generate the matrix from executable AWS conformance plus LG public profile declarations plus Agora additive-governance results.
- Separate columns: AWS-original, LG-enterprise, Agora-open.
- AWS column shows executable PASS/PARTIAL/FAIL/NOT_APPLICABLE.
- LG column may show only declared public target status until a dedicated LG rule provider exists; never present target declaration as implementation PASS.
- Agora-open column reports additive governance evidence separately.
- Every non-empty implementation claim links/references repository evidence.
- Explicitly label deliberate differences and non-evaluated/private behavior.
- Add a deterministic checker that fails when the checked-in matrix differs from regeneration.
- Add the checker to verify_all.py so release CI fails on documentation drift.
- Marketplace README/listing/claim register consume the generated evidence matrix.

## Acceptance criteria
- [x] Generated matrix has AWS-original, LG-enterprise and Agora-open columns.
- [x] AWS statuses are derived from conformance rules, not manually typed.
- [x] LG target declarations are clearly distinguished from implementation conformance.
- [x] Agora additive governance is not counted as AWS fidelity.
- [x] Every PASS/PARTIAL/FAIL AWS row includes evidence/remediation where appropriate.
- [x] Generated content contains no endorsement/certification claim.
- [x] Check script returns non-zero on drift.
- [x] verify_all.py includes the matrix drift check.
- [x] Marketplace docs link to/use the generated matrix.
- [x] Tests cover deterministic regeneration and drift failure.

## Negative cases
- generated matrix edited by hand;
- missing generated file;
- unsupported claim wording;
- LG target rendered as PASS;
- AWS result without evidence/remediation;
- additive Agora governance mixed into base AWS score.

## Focused verification
- uv run pytest -q tests/test_marketplace_evidence.py
- uv run python scripts/check_marketplace_evidence.py
- uv run ruff check src/agora_ai_sdlc/marketplace_evidence.py scripts/check_marketplace_evidence.py tests/test_marketplace_evidence.py
- uv run ruff format --check src/agora_ai_sdlc/marketplace_evidence.py scripts/check_marketplace_evidence.py tests/test_marketplace_evidence.py

## Full verification
- uv run python scripts/verify_all.py

## Dependencies
#95 and #96 implementation are required. #96 was merged into the #95 branch after #95 reached main; promotion PR #111 carries #96 into main. This issue is stacked on that promotion commit.

## Clarifications
None required. Until an LG rule provider exists, the matrix must show LG as a public target declaration, not as measured implementation compatibility.

## Completion evidence
- CI commands/results in TESTS.md.
- summary in RESULT.md.
- independent review in REVIEW.md before merge.
