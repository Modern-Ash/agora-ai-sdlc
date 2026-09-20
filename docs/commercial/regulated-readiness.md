---
package: regulated-readiness
implemented_assets:
  method_packs: [ai-sdlc]
  profiles: [regulated, enterprise, operational-evidence]
  policies: [data-classification, independent-review, model-provenance, runtime-selection]
---
# Regulated Delivery Readiness

## Customer problem

A team that delivers with AI assistance under higher-assurance expectations needs to know which technical controls the software enforces, which obligations remain with the organization, and what evidence would support an independent assessment, without treating the software as a certification.

## Entry criteria and prerequisites

- An accepted pilot or equivalent evidence that the method fits at least one representative workflow.
- Named executive sponsor plus security, compliance, legal, product, and repository owners, and a named Governance Owner able to authorize exceptions.
- Human actors available for the Product Owner and Quality Reviewer roles, each able to hold an active signing identity managed under the customer's key-management process.
- The customer's own list of applicable obligations, prepared with qualified compliance and legal advisers.
- Customer-operated source control, CI, monitoring, backup, retention, and identity processes.

## Activities

1. Map the customer's stated obligations to the [Regulated profile](../profiles/regulated.md) controls and to the [shared-responsibility model](security-and-responsibility.md), recording each item as software-enforced, deployment evidence, customer operation, or provider duty.
2. Configure and validate a non-production project: signed critical actions, role segregation, human approval roles, complete observed provenance, exception authority, and evidence-retention metadata.
3. Run the credential-free `regulated` sample and a customer-selected non-production Unit of Work, and record which controls held and which failed.
4. Rehearse a signed-forward recovery and a key-revocation procedure using customer-controlled non-production keys.
5. Produce a gap register and an evidence index for the customer's assessor; hand over runbooks and hold a readiness review.

## Deliverables and traceability

| Deliverable | Label | Evidence boundary |
| --- | --- | --- |
| Signed critical actions, role segregation, human-final approval, and complete observed-provenance checks | Implemented capability | Profile and Agora Core behavior exercised by `agora-ai-sdlc run-sample regulated` and repository tests |
| Time-bound authorized exception records and evidence-retention metadata | Implemented capability | Immutable project metadata and references; not WORM storage or legal hold |
| Control mapping of stated obligations to software, deployment evidence, customer operation, and provider duties | Consulting work | Based on the customer's obligation list; not legal advice |
| Gap register, evidence index, runbooks, and readiness review | Consulting work | Non-production evidence from the agreed project |
| Key-management, retention, and recovery rehearsal notes | Consulting work | Customer-controlled non-production material only |

## Responsibilities

| Customer | Modern Ash |
| --- | --- |
| Own the applicable obligations, legal and compliance interpretation, identity proofing, private-key custody and rotation, retention periods, legal holds, infrastructure isolation, access control, monitoring, incident response, and independent assurance | Configure and test shipped profile behavior, document its boundaries, and facilitate the mapping, rehearsals, and readiness review |
| Authorize exceptions, accept residual risk, and operate the production environment | Identify which controls are software-enforced and which remain customer or third-party responsibilities, and avoid certification claims |
| Provide trustworthy runtime observations for provenance | Show where a reviewed runtime adapter must supply observed values the software cannot infer |

## Baseline and success metrics

Record the customer's current evidence for signed changes, segregation of duties, approval records, model and runtime provenance, exception handling, and retention before the engagement. Success means the agreed non-production project passes the profile checks, the gap register is accepted with owners for every open item, and recovery and key-revocation rehearsals are documented. Reduced audit effort, faster assessments, or a favorable assessment outcome are customer-agreed **Goals** and are not guaranteed.

## Planning assumptions

An illustrative planning range is four to eight weeks for one representative project with existing CI, key management, and named control owners. This is not a schedule commitment. Number of obligations, evidence maturity, integration work, and assessor availability affect duration.

## Exclusions

Certification, attestation, audit opinions, legal or regulatory advice, identity proofing, key custody, hardware security modules, WORM or legal-hold storage, time attestation, hosted control plane, multi-user Studio, production operations, provider or model contracts, and 24x7 support are excluded unless separately contracted and technically available. Passing profile checks shows only that the declared technical contract was satisfied for the evaluated repository state.

## Exit criteria and acceptance

- The agreed non-production project validates against the profile, with every failed check explained.
- The gap register lists each open item with an owner and its category (software, deployment evidence, customer operation, or provider duty).
- Recovery and key-revocation rehearsals are documented, and runbooks are accepted by the customer's control owners.
- No output states that the software, the organization, or a deployment is certified or compliant.

Commercial and license boundaries are defined in the [package overview](README.md).
