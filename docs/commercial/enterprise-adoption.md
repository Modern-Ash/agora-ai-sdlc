---
package: enterprise-adoption
implemented_assets:
  method_packs: [ai-sdlc]
  profiles: [enterprise, operational-evidence, regulated]
  policies: [data-classification, independent-review, model-provenance, runtime-selection]
---
# Enterprise Adoption

## Customer problem

Multiple teams need consistent AI-SDLC policy and auditable project-local state while retaining control of infrastructure, providers, identities, credentials, repositories, and operational evidence.

## Entry criteria and prerequisites

- An accepted pilot or equivalent evidence that the method fits at least one representative workflow.
- Executive sponsor plus named platform, security, compliance, product, and repository owners.
- Customer-operated source control, CI, artifact distribution, monitoring, backup, identity, and key-management processes.
- A reviewed repository inventory, rollout groups, provider policy, budget dimensions, metric identifiers, and exception authority.
- Public Ed25519 trust roots and a customer-controlled location for signed immutable registry releases; private keys remain customer-managed.

## Activities

1. Define organization policy and project customization boundaries using the [Enterprise profile](../profiles/enterprise.md).
2. Design and test signed registry publishing, preview, project-local installation, forward upgrade, key rotation, and recovery procedures.
3. Configure representative projects and validate allowed providers, budget ceilings, required metrics, and time-bounded exception records.
4. Establish rollout waves, per-project reporting, change control, training, and operational ownership.
5. Optionally assess [Regulated profile](../profiles/regulated.md) readiness; this is control-gap consulting, not certification or legal advice.

## Deliverables and traceability

| Deliverable | Label | Evidence boundary |
| --- | --- | --- |
| Validated Enterprise configuration and signed project-registry workflow | Implemented capability | File/automation rollout; no hosted registry or fleet transaction |
| Previewed install/upgrade checksums, signers, provenance, and recovery point | Implemented capability | Per project and selected release |
| Provider, budget, metric, and exception policy validation | Implemented capability | Declared configuration; not proof a provider/exporter ran |
| Organization policy design, rollout plan, runbooks, and training | Consulting work | Customer-specific operating model |
| Regulated-readiness gap assessment when selected | Consulting work | Maps technical controls and external responsibilities; no certification |

## Responsibilities

| Customer | Modern Ash |
| --- | --- |
| Own identities, private keys, credential custody, provider/model terms, data residency, infrastructure isolation, repositories, CI, monitoring, backups, retention, and incident response | Configure and test shipped profile behavior, document boundaries, and facilitate rollout/recovery exercises |
| Publish and protect registry releases, approve policy, operate rollout automation, and make exception/risk decisions | Supply customer-specific policy examples, runbooks, training, and evidence of performed service activities |
| Obtain legal/compliance guidance and operate independent assurance | Avoid certification claims and identify controls that remain customer or third-party responsibilities |

## Baseline and success metrics

Measure current project onboarding time, policy drift, registry versions, failed updates, provider exceptions, evidence completeness, exported metric coverage, and recovery exercise results where sources exist. Success means the agreed rollout cohort validates against approved policy, signed updates and recovery are demonstrated on representative non-production projects, and owners accept the runbooks. Fleet-wide speed, cost, compliance, or quality improvements remain customer-agreed **Goals**, not guarantees.

## Planning assumptions

An illustrative planning range is six to twelve weeks for a limited first cohort with existing CI, key management, artifact hosting, and platform ownership. This is not a schedule commitment. Repository count, policy variance, integration work, assurance requirements, and organizational change affect duration.

## Exclusions

Hosted registry, SaaS control plane, tenancy, multi-user Studio, identity provider implementation, key custody, cloud landing zones, provider contracts, managed CI, production operations, compliance certification, legal advice, independent audit, and 24x7 support are excluded unless separately contracted and technically available.

## Exit criteria and acceptance

- The agreed cohort has per-project validation and rollout status with unresolved failures identified.
- A signed release is previewed and applied, and a signed forward recovery release is rehearsed in an approved non-production project.
- Policy, runbooks, responsibilities, training, known gaps, and operational owners are accepted.
- Any regulated-readiness output distinguishes implemented controls from deployment duties and external assurance.

Commercial and license boundaries are defined in the [package overview](README.md).
