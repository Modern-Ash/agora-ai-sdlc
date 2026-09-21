# Competitive positioning

Internal planning note, not buyer-facing copy. It records what may be said when Modern Ash positions Agora AI-SDLC against the published AI-driven development method definition, and what evidence stands behind it. Buyer-facing wording still goes through the [claim register](marketplace/claim-substantiation.md) and the [pre-submission review](marketplace/review-checklist.md).

## Scope of any comparison

- Compare against the **published method definition** (the AWS blog post and paper cited in the [alignment table](../reference/aws-ai-dlc-mapping.md)), reviewed on 2026-09-21. Do not make statements about any AWS product, service, tool or roadmap: this repository has no evidence about them.
- "The published definition does not specify X" is a statement about that document at that date. It must not be turned into "AWS lacks X".
- Agora is not sponsored, endorsed, or certified by AWS or another provider, and must not use AWS or partner marks or imply affiliation.

## Parity with the published method

The [alignment table](../reference/aws-ai-dlc-mapping.md) is the source of truth. Today the three phases, the plan-clarify-decide-execute-validate pattern, Intent, Units of Work, Bolts, user stories, non-functional requirements, risk and measurement records, domain and logical design, deployment units, operations, persistent traced artifacts, and both facilitated sessions have a counterpart. Open items: a recursive Level 1 Plan per pathway (a `plan` artifact exists but the process is not enforced) and the decisions on lifecycle shape and role count.

## Differentiators and their evidence

| Differentiator | Evidence | Permitted wording | Do not say |
| --- | --- | --- | --- |
| Runtimes, providers and models are replaceable; no provider SDK or cloud dependency | [ADR-0002](../decisions/ADR-0002-no-embedded-llm-sdk.md), multi-runtime conformance matrix, secret-leak and offline tests | "Provider-neutral and runs offline in its default checks" | That every provider has a bundled adapter or was live-tested |
| Gates, evidence and approvals are enforced by Agora Core and fail closed | Lifecycle, early-gate and late-gate tests; new-product sample | "Transitions require recorded evidence and approvals" | That it prevents defects or guarantees quality |
| Independent review with model and provider provenance | Independent-review and provenance policies and tests | "Same-actor or same-provider review is rejected deterministically where the profile requires distinct providers" | That provenance is observed when Core only records declared values |
| Signed actions, segregation of duties, retention metadata (Regulated profile) | `regulated` sample and tests | "Technical controls to support higher-assurance delivery" | Certification, compliance or audit outcomes |
| Budgets, governed fallback, data-eligibility policy | Runtime-selection and data-classification tests | "Runtime choice is explainable and budget-aware" | Cost savings |
| Reproducible offline conformance | Self-test and sample inventory | "One command runs the local conformance suite" | Production readiness |
| Live process view for people | Studio projection, Chromium tests | "Read-only dashboard of lifecycle, blockers and provenance" | That it replaces the CLI or hosts multiple users |
| Apache-2.0 software separate from paid services | LICENSE, package overview | "Open-source software with optional services" | That services are required or included |

## What must not be claimed

Superior speed, quality, accuracy or cost; productivity or defect-rate improvements; adoption or customer counts; anything about an AWS product; certification of any kind. Offline pilots measure workflow facts (blocks, gates, test counts), not delivery outcomes; only a customer pilot with a baseline can support an outcome claim, and then only as an agreed goal.

## Marketplace constraints to resolve first

1. Marketplace Professional Services listings must relate to an AWS service or public Marketplace product; a cloud-neutral method does not establish that alone. An accountable marketplace owner validates eligibility in the seller portal.
2. Terms associated with the published method (its name, Bolt, Mob Elaboration, Mob Construction) may be third-party marks or brand terms. This repository uses descriptive names for its rituals; legal review decides whether any of those terms may appear in listing copy.
3. Comparative statements need legal review under the marketplace's seller terms before submission.
4. Regulated Delivery Readiness stays out of the listing until its claims are substantiated.

## Next evidence to build

A customer or design-partner pilot with a measured baseline; Core support for observed provenance and artifact-scoped reviews (open Core work); the remaining alignment decisions; a published statement of what is measured offline versus in live pilots.
