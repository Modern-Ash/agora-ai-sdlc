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
