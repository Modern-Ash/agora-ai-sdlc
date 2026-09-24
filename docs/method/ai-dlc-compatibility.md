# AI-DLC method compatibility

Agora AI-SDLC targets faithful execution of the AI-Driven Development Lifecycle (AI-DLC) method while remaining independent of a specific cloud, LLM vendor, IDE or agent runtime.

This document is a method-compatibility contract, not a certification claim.

## Method boundary

AI-DLC defines the delivery method. Agora provides an executable implementation of that method:

- AI initiates the delivery conversation after the human supplies the Intent.
- Humans validate, adjust and approve at meaningful decision points.
- The Level 1 Plan is proposed from the Intent rather than selected from a hard-wired workflow.
- Plans are recursively decomposed into cohesive Units, Bolts and executable work.
- Design is part of the method, not an optional afterthought.
- Artifacts persist as linked context memory with backward and forward traceability.
- Brownfield delivery performs semantic elevation before material code change.
- Inception, Construction and Operations remain the macro lifecycle phases.
- Fast cycles are expected to operate in hours/days, not traditional multi-week sprint cadence.

## AI-DLC to Agora mapping

| AI-DLC concept | Agora implementation |
| --- | --- |
| Intent | Durable Core Intent plus source provenance |
| AI reverses conversation direction | Continuous Agora Flow wizard proposes the next action and asks bounded questions |
| Level 1 Plan | plan artifact plus recursive adaptive planning contracts |
| User Stories | user-stories artifact |
| Acceptance Criteria | requirement criteria with deterministic trace coverage |
| NFR | nfr artifact |
| Risk Register | risk-register artifact |
| Measurement Criteria | measurement-criteria artifact |
| PRFAQ | optional prfaq artifact |
| Unit | unit-of-work artifact |
| Bolt | bolt-plan artifact and Bolt execution model |
| Domain Design | domain-model artifact |
| Logical Design | logical-design plus compatible architecture/ADR artifacts |
| Code + tests | governed executor sessions plus verification evidence |
| Deployment Unit | deployment-unit artifact |
| Operations | deployment, operational readiness, observability and learning profiles |
| Brownfield static model | static-system-model |
| Brownfield dynamic model | dynamic-system-model |
| Context memory | linked artifact graph |
| Forward/back traceability | deterministic Context Graph |
| Human loss-function checkpoints | Core gates, approvals and wizard confirmation boundaries |

## Inception contract

A faithful Agora Inception should progressively enrich the Intent with:

1. material clarifications;
2. Level 1 Plan;
3. User Stories and Acceptance Criteria;
4. NFRs;
5. risks;
6. Measurement Criteria;
7. cohesive Units;
8. suggested Bolts;
9. optional PRFAQ when the business/customer narrative adds value.

The user should not have to author prompts for any of these steps. The wizard explains what Agora understood, what is missing, what it proposes and what confirmation means.

## Construction contract

Construction is semantic, not merely code generation:

1. for brownfield, establish static/dynamic semantic models first;
2. Domain Design models business behavior independent of infrastructure;
3. Logical Design applies NFRs, patterns and explicit trade-offs;
4. implementation follows validated design and acceptance contracts;
5. tests are generated/executed and their evidence is traced back to criteria;
6. an operations-ready Deployment Unit packages executable/configuration/evidence.

Human validation is continuous across these steps rather than deferred to a single final review phase.

## Operations contract

Operations includes deployment readiness, rollout decisions, telemetry/observability, runbook-informed recommendations and learning feedback. Production authority remains explicit and human/governance controlled.

## Agora extensions

The following are Agora implementation choices that add operational value without changing AI-DLC semantics:

### Progressive Intelligence

Agora chooses the least expensive sufficient intelligence layer:

    deterministic Core -> Laya System-1 -> local/free generative executor -> external/frontier executor -> human

This is an efficiency policy, not a new lifecycle.

### Context Economy

Agora deterministically forms the candidate context, lets Laya prune only that candidate set, keeps changed/dirty and uncertain files fail-open, and exposes before/after context estimates to the user.

### Executable governance

AI-DLC human oversight is represented as durable Core gates, evidence, roles and approvals instead of being left only in prompt instructions.

### Transparent wizard

The normal UX is one continuous session. Every screen states:

- current AI-DLC phase/substep;
- facts Agora is using;
- open gaps;
- method outputs/evidence;
- proposed next action;
- executor/decision source when AI is used;
- approximate context economy;
- human authority boundary.

Operational complexity is abstracted, but no evidence or decision provenance is hidden.

## Non-goals

Agora must not:

- turn adaptive pathways into hard-wired AI-DLC workflows;
- silently approve human-owned decisions;
- claim an artifact exists merely because the current Core gate does not require it;
- use a generative model where deterministic evidence is sufficient;
- require users to copy methodology prompts for the normal workflow;
- make AWS-specific services part of the core method semantics.

Compatibility profiles may map the neutral method to AWS or other enterprise environments without changing the canonical lifecycle meaning.
