---
package: starter-pilot
implemented_assets:
  method_packs: [ai-sdlc]
  profiles: [starter, github-delivery, generic-ci-evidence, security-findings]
  policies: [data-classification, independent-review, model-provenance, runtime-selection]
---
# Starter Pilot

## Customer problem

A team needs to evaluate governed AI-assisted delivery on real but bounded work without committing to an enterprise rollout or coupling its method to one model provider.

## Entry criteria and prerequisites

- One team, one Git repository, and one non-production or otherwise reversible Unit of Work.
- Named human Product Owner and distinct human Quality Reviewer with authority to accept the pilot.
- Compatible Agora Core, local Git, and customer-selected runtimes already available where live execution is desired.
- Approved data classification and no requirement to place provider credentials in Agora project state.
- Testable acceptance criteria and access to the repository's normal CI process.

## Activities

1. Confirm pilot scope, baseline measurements, roles, depth, runtime declarations, and evidence plan.
2. Preview and apply the [Starter profile](../profiles/starter.md) to the selected repository.
3. Facilitate clarification, design, implementation, independent review, CI evidence, rework, and human acceptance for one Unit of Work.
4. Exercise provider replacement when two customer-approved runtimes are available; otherwise record it as untested.
5. Run validation, capture the result and limitations, and hold an adoption retrospective.

## Deliverables and traceability

| Deliverable | Label | Evidence boundary |
| --- | --- | --- |
| Previewed Starter configuration and initialized local project | Implemented capability | One team/repository; no credential discovery or runtime installation |
| Core lifecycle records, artifacts, approvals, and gate evidence | Implemented capability | Exact pilot Unit of Work and repository revision |
| Provider-neutral review and provenance assessment | Implemented capability | Only observed/declared fields at their recorded trust level |
| Pilot plan, facilitation, configuration, and training | Consulting work | Customer-specific delivery under the agreed statement of work |
| Baseline/outcome report and rollout recommendation | Consulting work | Measured pilot facts separated from goals and extrapolations |

## Responsibilities

| Customer | Modern Ash |
| --- | --- |
| Own repository access, backups, branch protection, CI, provider accounts/terms, credentials, data approval, and production decisions | Configure the bounded pilot, explain controls, facilitate workflow, and preserve evidence boundaries |
| Supply Product Owner, independent reviewer, domain expertise, acceptance criteria, and timely decisions | Record clarifications, blockers, deviations, and delivered artifacts without manufacturing evidence |
| Operate runtimes and approve any network/provider use | Use only customer-approved execution paths and never retain provider secrets in repository artifacts |

## Baseline and success metrics

Before execution, record the current test baseline, typical lead/review time if available, evidence completeness, clarification age, rework count, and runtime/cost observations that the customer can measure. Pilot success is acceptance of the selected Unit of Work, successful `agora validate`, explicit review separation, and a documented go/no-go decision. Faster delivery, lower cost, fewer defects, or higher throughput are **Goals**, not guaranteed percentages.

## Planning assumptions

An illustrative planning range is two to four weeks for one prepared team and one bounded Unit of Work. This is not a schedule commitment. Scope ambiguity, missing tests, provider onboarding, security review, integration work, or slow decisions extend the engagement.

## Exclusions

Multi-team rollout, hosted control plane, multi-user Studio, managed credentials, custom provider adapters, production deployment, 24x7 support, model certification, and promised productivity gains are excluded unless a later package or statement of work explicitly covers them.

## Exit criteria and acceptance

- Starter state validates and the caller repository's pre-existing files remain governed by customer change control.
- The Unit of Work is accepted or ends with a documented blocker and recovery recommendation.
- The report includes baseline, outcome, evidence, limitations, untested claims, and customer decisions.
- The acceptance owner signs off the deliverables and next-step recommendation.

Commercial and license boundaries are defined in the [package overview](README.md).
