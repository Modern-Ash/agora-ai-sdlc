---
package: legacy-modernization
implemented_assets:
  method_packs: [ai-sdlc]
  profiles: [modernization, generic-ci-evidence, security-findings, operational-evidence]
  policies: [data-classification, independent-review, model-provenance, runtime-selection]
---
# Legacy Modernization

## Customer problem

A legacy system needs incremental change without inventing undocumented behavior, hiding accepted differences, or treating generated conversion output as proof of semantic equivalence.

## Entry criteria and prerequisites

- One bounded system area and a candidate independently deployable migration slice.
- Named Product Owner, domain experts, technical owner, independent reviewer, operator, and rollback decision owner.
- Customer-controlled source, build/test environment, representative test data, dependency access, backup, deployment, and rollback capabilities.
- Agreement on data classification, evidence retention, allowed tools/runtimes, unknown-behavior treatment, and production boundary.

## Activities

1. Establish legacy inventory, dependency map, and behavior characterization with known evidence and explicit unknowns.
2. Define target architecture, migration plan, and one traced slice using the [Modernization profile](../profiles/modernization.md).
3. Perform or support customer-approved conversion work and record exact inputs, tools, procedures, outputs, and exceptions.
4. Compare characterized behavior, reject regressions or missing evidence, and route accepted differences to Product Owner decision.
5. Prepare cutover, rollback validation, stabilization evidence, and a recommendation for the next slice.

## Deliverables and traceability

| Deliverable | Label | Evidence boundary |
| --- | --- | --- |
| Profile-validated inventory-to-stabilization trace | Implemented capability | Registered artifacts and evidence for the selected slice |
| Failed-closed equivalence, cutover, rollback, and stabilization assessments | Implemented capability | Characterized cases only; not arbitrary semantic proof |
| Discovery, reverse engineering, conversion, and test support | Consulting work | Customer-approved tools and bounded system context |
| Cutover/rollback rehearsal facilitation and evidence report | Consulting work | Approved environment; production execution only if separately authorized |
| Slice outcome and next-wave recommendation | Consulting work | Measured facts, unknowns, accepted differences, limitations, and goals |

## Responsibilities

| Customer | Modern Ash |
| --- | --- |
| Own system truth, licenses, source/data access, environments, credentials, backups, production traffic, retirement, risk acceptance, and business decisions | Facilitate profile workflow, maintain traceability, mark unknowns, and document performed analysis/conversion work |
| Supply domain experts and approve characterization, accepted differences, cutover, rollback, and acceptance | Avoid claiming generated inventory or tests are complete; surface regressions and missing evidence |
| Operate deployments and incident response unless explicitly scoped otherwise | Support agreed rehearsals and deliver evidence/limitations for the bounded slice |

## Baseline and success metrics

Measure characterized behavior count, known/unknown split, dependency coverage, baseline and resulting test outcomes, unexplained regressions, accepted differences, rollback rehearsal result, stabilization observations, effort, and elapsed time for the slice. Success means the bounded slice meets its accepted criteria with traceable current evidence and an accountable cutover or no-go decision. Throughput, defect reduction, cloud cost, retirement date, or automation percentage are **Goals**, not guaranteed outcomes.

## Planning assumptions

An illustrative planning range is six to sixteen weeks for one bounded slice with accessible source, executable tests, domain experts, and a non-production rehearsal environment. This is not a schedule commitment. Missing buildability, sparse tests, unsupported dependencies, data constraints, production windows, and unresolved behavior increase duration or block exit.

## Exclusions

Whole-system rewrite, automatic semantic proof, invented baselines, unsupported license remediation, production deployment authority, data migration, infrastructure procurement, disaster recovery ownership, system retirement, compliance certification, and ongoing managed operations are excluded unless separately scoped.

## Exit criteria and acceptance

- Inventory, characterization, plan, slice, conversion, equivalence, cutover, rollback, and stabilization records trace consistently.
- Unknown behavior remains explicit; regressions are corrected or block exit; accepted differences have evidence and Product Owner acceptance.
- Rollback is validated in the agreed environment and the customer owns the production/no-go decision.
- The acceptance owner approves the slice report, limitations, unresolved risks, and next-wave recommendation.

Commercial and license boundaries are defined in the [package overview](README.md).
