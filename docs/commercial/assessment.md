---
package: ai-sdlc-assessment
implemented_assets:
  method_packs: [ai-sdlc]
  profiles: [starter, github-delivery, generic-ci-evidence, security-findings, operational-evidence]
  policies: [data-classification, independent-review, model-provenance, runtime-selection]
---
# AI-SDLC Assessment

## Customer problem

Teams adopting AI-assisted delivery often lack a measured baseline, explicit human accountability, evidence gates, and a provider-replacement plan. This package identifies those gaps without treating model output or tool configuration as proof of delivery quality.

## Entry criteria and prerequisites

- An accountable sponsor and named engineering, product, security, and operations participants.
- One representative repository and delivery workflow selected for analysis.
- Customer-approved, read-only access to relevant process documents and sanitized evidence. No production credentials are required by Agora.
- Agreement on data classification, interview boundaries, baseline period, and who may accept the assessment.

## Activities

1. Facilitate workflow, role, approval, evidence, integration, and data-boundary discovery.
2. Map the observed workflow to the [AI-SDLC Method Pack](../method/overview.md), depth profiles, and provider-neutral policies.
3. Run the credential-free [self-test](../reference/self-test.md) and relevant samples against the distributed software.
4. Record capability matches, gaps, external responsibilities, risks, and candidate pilot scope.
5. Review findings and prioritize a staged adoption backlog with accountable owners.

## Deliverables and traceability

| Deliverable | Label | Evidence boundary |
| --- | --- | --- |
| Installed-distribution conformance result | Implemented capability | `agora-ai-sdlc self-test --json`; offline package behavior only |
| Method, profile, policy, and integration fit matrix | Consulting work | References current manifest assets and observed customer workflow |
| Baseline metric workbook and evidence inventory | Consulting work | Customer-supplied measurements with source and observation period |
| Risk, responsibility, and gap report | Consulting work | Separates Agora controls from customer/deployment controls |
| Recommended pilot scope and adoption backlog | Consulting work | Prioritized proposal; not an authorization to implement |

## Responsibilities

| Customer | Modern Ash |
| --- | --- |
| Provide authorized participants, repository/process context, sanitized evidence, and source owners | Facilitate discovery, validate shipped capabilities, and document evidence boundaries |
| Decide data classification, acceptable access, business priorities, and risk ownership | Avoid collecting credentials and mark unknown or unavailable evidence explicitly |
| Validate factual findings and accept or reject recommendations | Correct factual errors and deliver the agreed assessment artifacts |

## Baseline and success metrics

Measured baselines may include Unit-of-Work lead time, clarification age, rework count, gate rejection reasons, review independence coverage, evidence completeness, and runtime cost/usage where customer records exist. A successful engagement means the agreed sources, period, owners, gaps, and pilot decision are documented and accepted. Any improvement target is a **Goal** set after baseline review; no productivity, cost, quality, or delivery percentage is guaranteed.

## Planning assumptions

An illustrative planning range is one to two weeks for one repository and one delivery workflow, assuming timely access and participant availability. This is not a schedule commitment; repository count, evidence quality, regulated obligations, languages, integrations, and stakeholder availability change the estimate.

## Exclusions

Production changes, provider credential setup, custom adapters, Studio implementation, compliance certification, legal advice, penetration testing, cloud migration, and ongoing support are excluded unless separately scoped. The assessment does not certify model quality or infer missing baselines.

## Exit criteria and acceptance

- Every agreed source is marked reviewed, unavailable, or out of scope.
- Findings distinguish measured facts, customer statements, assumptions, and goals.
- Deliverables identify implemented capabilities versus consulting work and external responsibilities.
- The customer acceptance owner approves the report or records specific unresolved observations.

Commercial and license boundaries are defined in the [package overview](README.md).
