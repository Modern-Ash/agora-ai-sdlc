## Start / Inception flow

When `aisdlc start` creates or reuses a durable Intent, treat the generated
`.agora/ai-sdlc/handoffs/<intent>/INCEPTION_HANDOFF.md` as the execution contract.

The selected runtime is only the executor. Provider/model choice must not change method semantics.

Mandatory Inception sequence:

1. Read the durable Intent and its source issue.
2. Load only bounded repository context referenced by the issue plus AGENTS.md.
3. Separate source facts from AI proposals.
4. Ask only material clarification questions. Group related choices into one human decision card where practical.
5. Produce a Level 1 Plan before producing the final artifact.
6. Decompose the Intent into cohesive Units.
7. Suggest small Bolts for those Units.
8. Trace acceptance criteria to the source issue.
9. Identify risks, constraints and dependencies.
10. Persist proposals using existing AI-SDLC artifact contracts where they apply.
11. Stop for human review before Construction.

### Inception output contract

A Start/Inception response is incomplete unless it contains all of:

- Intent interpretation
- Material clarifications requiring human decision
- Level 1 Plan
- Proposed Units
- Suggested Bolts
- Acceptance criteria trace
- Risks, constraints and dependencies
- Product decisions explicitly marked as source fact, AI proposal, or human-selected decision
- Files created or modified
- Human decision required to continue

Do not jump directly from Intent to implementation or directly to a final product artifact without first presenting the Level 1 Plan and decomposition.

When several material choices are open, prefer one compact decision card with options, recommendations and trade-offs instead of making the human answer one prompt per low-level primitive.

Human decisions made in conversation are not equivalent to durable Agora approval evidence. Until a first-class decision record exists, artifacts must not label conversational choices as auditable approvals.

## Before presentation to the human

A parseable proposal is not an execution authorization. Use canonical templates and
validate every persisted Plan/Unit/Bolt and its references before presenting it.
Keep pending approvals pending. Group related material choices into one card,
identifying the exact revisions and scope; do not equate Plan approval to Bolt
Plan approval. A contradiction with an existing decision requires clarification,
not an agent-invented reinterpretation. Reuse valid recorded decisions; obtain
explicit human confirmation for a new approval or an invalidated revision.
