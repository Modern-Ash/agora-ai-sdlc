# Agora AI-SDLC Guided Delivery Skill

Use this skill when operating a project installed with Agora AI-SDLC.

## Purpose

Reduce user-facing ceremony without weakening governance.

The human should interact with intent, clarification, proposals, approvals, and review. The agent may wrap Agora Core commands, but Core remains the lifecycle authority.

## Mandatory rules

1. Inspect governed state before acting.
2. Never reimplement gate logic. Query Agora Core and obey its result.
3. Translate raw blockers into concise human language.
4. Never record a human approval without explicit confirmation in the current interaction.
5. Never transfer a human-owned role just to make progress.
6. AI-generated artifacts are proposals until the responsible human accepts them.
7. Preserve producer/reviewer separation.
8. Do not expose credentials, secrets, child PII, or provider tokens in artifacts or prompts.
9. Use packaged AI-SDLC templates for known artifact kinds.
10. Stop when Core denies a transition; explain the remaining obligation instead of bypassing it.

## Default interaction

Start with:

```bash
agora-ai-sdlc continue
```

When attached to a terminal, this command is an interactive session. The human chooses actions and may
select or change among responsive locally detected assistants. Keep the selected assistant for the
session until the human changes it. Do not treat runtime selection as approval or role transfer.

Use `--non-interactive` only when a one-shot projection is required.

Use:

```bash
agora-ai-sdlc continue --expert
```

only when exact gate/blocker details are needed.

For command transparency use:

```bash
agora-ai-sdlc continue --commands
```

For machine-readable clients use:

```bash
agora-ai-sdlc continue --json
```

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

## Readiness vertical slice

When the current gate requires `readiness-assessment`, clarification, and Product Owner approval:

### A. Prepare the readiness assessment

Use the packaged template `templates/readiness-assessment.md`.

Populate all required sections from bounded repository context:

- Problem and context
- Stakeholders and accountable owner
- Constraints and assumptions
- Open clarifications
- Data classification and eligible runtimes
- Readiness decision

Do not invent missing product facts. Put unresolved matters under **Open clarifications**.

Persist the accepted artifact at a predictable repository path such as:

```
docs/governance/<work>-readiness.md
```

Then register it:

```bash
agora artifact add \
  --swarm <swarm> \
  --work <work> \
  --kind readiness-assessment \
  --uri repo://docs/governance/<work>-readiness.md \
  --by <responsible-human-actor>
```

### B. Clarification

If the gate requires resolved clarifications, run the Core clarification operation using the configured compatible runtime/runner.

```bash
agora work clarify --swarm <swarm> --work <work> --by <actor>
```

If the responsible actor is human and has no runtime, do not transfer the role. Use the configured AI executor/runner only as assistance where Core supports that boundary. If Core cannot execute the clarification with the available configuration, stop and explain the missing runtime capability.

Relay material questions to the human. Do not convert agent suggestions into approvals.

### C. Human approval

After the artifact is accepted and clarifications are resolved, ask:

```
The readiness review is complete. Approve proceeding to the next governed stage?
```

Only after an explicit affirmative answer:

```bash
agora approval add \
  --swarm <swarm> \
  --work <work> \
  --role product-owner \
  --by <responsible-human-actor> \
  --note "Readiness reviewed and approved"
```

### D. Transition

Re-check:

```bash
agora next --swarm <swarm>
```

Then perform only the transition Core says is allowed:

```bash
agora work transition \
  --swarm <swarm> \
  --work <work> \
  --to <target> \
  --by <responsible-human-actor>
```

Re-run:

```bash
agora-ai-sdlc continue
```

## Presentation rules

Default output should show:

- current human-readable stage;
- what is already satisfied;
- what decision is needed;
- recommendation and rationale;
- available actions.

Do not lead with internal arrays such as `missing-artifacts=[...]`.

When the user asks for details, show:

- gate id;
- source/target state;
- artifact/evidence requirements;
- approval roles;
- clarification state;
- provenance/digest information where relevant.

## Agent portability

The same behavior applies to Claude Code, Codex, OpenCode, Ollama-backed agents, or any Markdown-aware executor. Provider/model selection must not change lifecycle meaning.


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
