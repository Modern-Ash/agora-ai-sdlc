# Collaborative rituals

The method uses two facilitated sessions in which AI proposes and a small group of people validates. They add no lifecycle states: each is a recorded way of producing the artifacts and approvals that Core gates already require. The published method this follows calls them Mob Elaboration and Mob Construction (see the [alignment table](../reference/aws-ai-dlc-mapping.md)); here they use descriptive names.

Both follow the [protocol](../../registry/methods/ai-sdlc/PROTOCOL.md): the AI plans and asks, the group decides, the AI executes, results are validated against evidence. Every decision that matters is recorded as a Core artifact, approval or evidence record, never only in conversation.

## Collaborative elaboration (Inception)

**Purpose.** Turn an intent into validated stories, non-functional requirements, risks, measures and Units of Work in one focused session instead of a long sequence of hand-offs.

**Participants.** A facilitator (any actor; usually the product-owner), the product-owner, developers, quality reviewers and other stakeholders. AI actors propose; humans hold the accountable roles.

**Flow.**

1. The AI asks clarifying questions about the intent. Answers are recorded with `agora work clarify` so unresolved questions block the gate.
2. The AI drafts [user stories](../../templates/user-stories.md), acceptance criteria and non-functional requirements ([requirements](../../templates/requirements.md)). The group corrects under- and over-engineered parts.
3. The AI groups cohesive stories into Units of Work ([unit-of-work](../../templates/unit-of-work.md)) that are loosely coupled and can be built in parallel, and proposes [Bolts](../../templates/bolt-plan.md) for each.
4. Risks ([risk-register](../../templates/risk-register.md)) and measures ([measurement-criteria](../../templates/measurement-criteria.md)) are added and traced to the intent. A [PRFAQ](../../templates/prfaq.md) is optional.
5. The accountable roles approve; the Core gate for the phase passes only with the recorded artifacts, resolved clarifications and approvals.

**Outputs.** Units of Work with stories and acceptance criteria, non-functional requirements, risk and measurement records, suggested Bolts, and the approvals that release the gate.

## Collaborative construction (Construction)

**Purpose.** Build each Unit through short Bolts with humans validating each step, and let teams working on different Units exchange integration specifications in the same session.

**Participants.** Developers holding the builder role, the quality-reviewer, the architect, and the AI actors executing the work.

**Flow per Bolt.**

1. The AI proposes the Bolt plan ([bolt-plan](../../templates/bolt-plan.md)); a human approves it before execution.
2. Domain model ([domain-model](../../templates/domain-model.md)), then logical design ([logical-design](../../templates/logical-design.md)) with decision records; humans review and choose between options.
3. The AI generates code and tests and executes them; results are recorded as evidence. Humans review failures and approve fixes.
4. Teams exchange integration specifications for neighboring Units as Unit artifacts, so each Bolt starts from validated context.
5. When the build gate is satisfied, deployable output is described in [deployment-units](../../templates/deployment-units.md) with its functional, security and non-functional test results.

**Recording.** A Bolt has no time tracking in Core; its plan, decisions and outcome are artifacts and evidence. AI sessions run through Core sessions so runtime, provider and model provenance is recorded.

## Brown-field work

Before the first Bolt, the AI elevates existing code into a concise model (static components and responsibilities, dynamic interactions for the important use cases) that people correct. The [Modernization profile](../profiles/modernization.md) captures this as inventory, dependency map and characterization.

## Facilitation rules

- One decision owner per approval; the record names the role and actor.
- Clarifications that are not answered stay open; do not proceed on assumption.
- A session that changes a validated artifact creates a new revision; earlier approvals do not carry over.
- Sessions can be run remotely; collocation is a recommendation, not a control the flavor enforces.
