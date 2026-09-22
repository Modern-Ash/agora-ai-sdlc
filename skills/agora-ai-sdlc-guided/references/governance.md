## Guided human-attention flow

When Core reports human attention:

1. Identify work, current state, target state, responsible role, and actor.
2. Explain required decisions in business language.
3. Prepare non-authoritative artifacts or analysis that the actor is allowed to assist with.
4. Show the proposal or concise diff to the human.
5. Ask one explicit approval question.
6. Only after an affirmative answer, record the approval with Agora Core.
7. Attempt the governed transition.
8. Re-read state after every mutation.

## Decision-card contract

Treat the guided projection as the primary human UI. Present, in this order:

1. **Objective** — the current work title and bounded outcome.
2. **Lifecycle context** — Method Pack, current stage, target stage and gate.
3. **Responsible authority** — role and actor that own the decision.
4. **Readiness checks** — artifacts, criteria, clarifications, evidence, repository policy and approvals.
5. **What remains** — concise human-language obligations.
6. **Responsibility boundary** — what AI may prepare versus what requires human authority.
7. **Recommended action** — one next interaction, not a list of low-level commands.
8. **Optional details** — command bundle, raw blockers, digests and structured state only when requested.

Do not make the normal UI look like a debugger.

## Command-bundle rules

The grouped command bundle exists for transparency, automation authors and expert troubleshooting. It is not the normal user workflow.

For each command include:

- the exact Core primitive;
- why it exists;
- whether it is read-only, AI-preparable, or human-authoritative;
- the condition that must be true before it runs;
- the expected state change or durable record.

Never present a sequence as safely executable end-to-end if one of its steps requires a fresh human decision.

For example:

```text
1. prepare docs/governance/first-work-readiness.md
   AI-preparable. Human must review before registration.

2. agora artifact add ...
   Records the accepted document in Core.

3. agora work clarify ...
   Resolves the Method Pack clarification obligation.

4. agora approval add ...
   HUMAN-AUTHORITATIVE. Execute only after explicit approval.

5. agora work transition ...
   Execute only after a fresh readiness check says the gate is satisfied.

6. agora-ai-sdlc continue ...
   Re-read Core and present the next decision.
```

## Interaction discipline

When several mechanical steps can be safely grouped, execute them as one agent operation and report the resulting durable state once.

Do not force the human through one prompt per primitive command. Stop only when:

- a material clarification requires human input;
- an approval belongs to a human role;
- Core denies the proposed mutation;
- a security/data-policy decision is required;
- the selected runtime lacks required capability;
- an independent review boundary is reached.

This preserves detailed governance while minimizing ceremony.
