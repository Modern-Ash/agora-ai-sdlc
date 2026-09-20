---
issue: 43
epic: 8
title: Prepare marketplace-ready Professional Services listing content
repository: Modern-Ash/agora-ai-sdlc
base_commit: d51dc62
status: review
risk: medium
context_size: medium
planner: Codex
created_at: 2026-09-20
---
# Task: Marketplace-ready Professional Services listing content

## Objective

Prepare reviewable AWS Marketplace Professional Services listing copy and submission inputs without submitting a product, inventing seller data, storing customer/pricing data, or presenting Agora as SaaS or AWS-specific software.

## Allowed paths

- `.agora/execution/43/`
- `docs/commercial/README.md`
- `docs/commercial/marketplace/`
- `tests/test_marketplace_content.py`

## Forbidden changes

- Product behavior, manifests, profiles, policies, Method Packs, samples, or packaging
- Marketplace submission, seller-account changes, pricing, buyer identifiers, customer data, credentials, or legal terms
- Claims of AWS sponsorship, certification, compliance, managed service, SaaS, guaranteed outcomes, or unsupported product capability

## Functional requirements

- Draft product title, short and long descriptions, highlights, categories, keywords, delivery method, support text, dimensions, additional-resource inputs, and private-offer inputs.
- Position the offer as Professional Services delivered under a statement of work and private offer, not SaaS.
- State that delivery may use customer-selected AWS infrastructure while Agora remains provider-neutral.
- Distinguish Apache-2.0 software, implementation services, engagement support, and excluded ongoing managed support.
- Tie every material marketing claim to local evidence through stable claim identifiers.
- Provide an editorial, legal, security, and marketplace-operations gate that remains blocked until accountable humans complete it.

## Acceptance criteria

- [x] Content does not imply AWS sponsorship or certification.
- [x] Delivery method matches the existing service packages.
- [x] No customer secrets, buyer identifiers, or prices are stored in the repository.
- [x] Listing distinguishes software, implementation, engagement support, and managed support.
- [x] Every marketing claim has a substantiation entry and evidence boundary.
- [x] Editorial/legal review checklist is present and blocks submission while incomplete.

## Negative cases

- Unregistered claim IDs, unsupported claims, numeric prices, AWS account IDs, credentials, or completed review boxes fail documentation tests.
- Missing Professional Services/private-offer positioning, AWS neutrality, support placeholders, or submission blockers fail documentation tests.
- Broken local evidence links fail documentation tests.

## Focused verification

- `uv run pytest tests/test_marketplace_content.py -q`
- `uv run ruff check tests/test_marketplace_content.py`

## Full verification

- `uv run python scripts/verify_all.py`

## Dependencies

- #41 provides implemented service-package boundaries.
- #42 provides the reference architecture and shared-responsibility model.
- The issue text refers to dependencies #40 and #41 by topic; current repository numbering places those completed topics in #41 and #42.

## Clarifications

The repository prepares content only. Seller eligibility, an eligible related AWS service or public Marketplace product, support contacts, logo, URLs, terms, buyer data, and pricing require accountable business input outside this issue and remain explicit submission blockers.

## Completion evidence

Documentation and verification in progress; independent editorial/legal review pending.
