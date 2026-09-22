# Starting real work with AI-SDLC

The recommended AI-SDLC-aligned entry point uses the short `aisdlc` alias (`agora-ai-sdlc` remains available):

```bash
aisdlc start --issue 11 --agent codex
```

The command is intentionally **not** an issue-to-code shortcut.

It performs the minimum AI-led intake needed before Inception work:

1. infer the current GitHub repository from `origin` unless `--project` is provided;
2. read the issue through the installed governed `github-issues` Tool adapter;
3. persist a draft Core Intent whose source is the issue;
4. select a responsive local AI runtime without reading credentials;
5. hand the Intent to AI for clarification, Level 1 Plan generation, Unit decomposition, and suggested Bolts;
6. stop at the human review boundary.

No Intent acceptance, plan approval, Unit/Bolt approval, or Construction is performed by `start`.

This preserves the AI-SDLC direction of travel: AI does planning and decomposition, while humans validate and moderate critical decisions. Core continues to own durable Tool Runs, Intent records, approvals, evidence, provenance, and traceability underneath the simplified UX.

## Example: Agorix

```bash
cd /home/faguero/dev-agora/agorix

aisdlc start \
  --issue 11 \
  --agent codex
```

If the Git remote cannot be inferred:

```bash
aisdlc start \
  --issue 11 \
  --project Modern-Ash/agorix \
  --agent codex
```

The expected stopping point is a draft Intent plus an AI handoff that asks the selected runtime to:

- inspect the issue and repository context;
- ask only material clarifying questions;
- propose the Level 1 Plan;
- propose cohesive Units;
- suggest one or more Bolts;
- return the proposal for human review before Construction.

The legacy `continue` command remains available for projects still using the 0.1.x lifecycle projection.
