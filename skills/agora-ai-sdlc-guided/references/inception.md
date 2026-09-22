## Start / Inception flow

When `aisdlc start` creates or reuses a durable Intent, treat the generated
`.agora/ai-sdlc/handoffs/<intent>/INCEPTION_HANDOFF.md` as the execution contract.

The selected runtime is only the executor. Provider/model choice must not change method semantics.

Mandatory Inception sequence:

1. Read the durable Intent and its source issue.
2. Load only bounded repository context referenced by the issue plus AGENTS.md.
3. Separate source facts from AI proposals.
4. Resolve candidate questions against the source issue and its referenced authoritative docs first. Ask the human only about ambiguity that remains material after that check. Group related choices into one human decision card where practical.
5. Select the narrowest applicable adaptive pathway from explicit source scope; never add engineering obligations that the pathway explicitly exempts.
6. Produce a Level 1 Plan before producing the final artifact.
7. Decompose the Intent into cohesive Units only where decomposition adds execution value.
8. Suggest small Bolts only where they improve execution/review boundaries; do not manufacture multiple Bolts for a single bounded documentation/trivial deliverable.
9. Trace acceptance criteria to the source issue.
10. Identify risks, constraints and dependencies.
11. Persist proposals using existing AI-SDLC artifact contracts where they apply.
12. Stop for human review before Construction.

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

When several material choices are open, prefer one compact decision card with options, recommendations and trade-offs instead of making the human answer one prompt per low-level primitive. A constraint already fixed by the issue or a referenced authoritative document is a source fact, not a clarification question.

Human decisions made in conversation are not equivalent to durable Agora approval evidence. Until a first-class decision record exists, artifacts must not label conversational choices as auditable approvals.

## Before presentation to the human

A parseable proposal is not an execution authorization. Use canonical templates and
validate every persisted Plan/Unit/Bolt and its references before presenting it.
Keep pending approvals pending. Group related material choices into one card,
identifying the exact revisions and scope; do not equate Plan approval to Bolt
Plan approval. A contradiction with an existing decision requires clarification,
not an agent-invented reinterpretation. Reuse valid recorded decisions; obtain
explicit human confirmation for a new approval or an invalidated revision.
