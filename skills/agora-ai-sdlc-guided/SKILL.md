---
name: agora-ai-sdlc-guided
description: Operate Agora AI-SDLC through portable multi-agent guidance with explicit authority, progressive phase context and human-only observability.
---
# Agora AI-SDLC Guided Delivery Skill

## Purpose and authority

Reduce user-facing ceremony without weakening governance. This skill wraps the
framework; Agora Core remains lifecycle authority. Runtime/model choice changes
the executor, never the meaning of a permission, decision or gate. Multi-agent
support does not mean launching multiple agents for every task.

## Always-active boundaries

1. Inspect the exact governed Work/revision and recorded branch before acting.
   Never substitute installer `first-work` for an issue-derived Intent.
2. Never reimplement gate logic. Query Core and obey its result. A status display
   or parseable artifact is not an execution authorization.
3. Never record a human approval without explicit confirmation. Existing durable
   approvals may be consulted only for the exact valid revision/scope; they are
   not blanket approval for later changes. Never transfer a human role to proceed.
4. Plan approval is not Bolt Plan approval. Before a Bolt, validate the current
   plan/revision/dependencies and check `assert_can_start` plus applicable Core
   authority. Pending means stop the affected execution, not just its status update.
5. Preserve producer/reviewer separation; never claim an independent review you
   did not perform. Agents' proposals are not human-selected decisions.
6. Do not expose secrets, tokens, child PII, private keys, raw prompts or transcripts.
7. Use packaged templates and validate proposals before asking for approval.
8. Group already authorized mechanical work. Ask only for material ambiguity,
   absent/invalid authority, policy decisions, non-convergence or budget exhaustion.
9. After a mutation, re-read Core. Do not mask a bypass with retroactive approval.

## Load only the phase you need

Use `aisdlc skill --phase <phase>` for this root plus one phase resource, or
`aisdlc skill --phase <phase> --json` for paths, hashes and byte sizes. JSON does
not include instruction content unless `--content` is explicit. Token counts are
not inferred from byte sizes. Do not load all resources on every turn.

- [Inception](references/inception.md): Intent interpretation, Level 1 Plan,
  cohesive Units, suggested Bolts, material decisions and proposal validation.
- [Construction](references/construction.md): bounded authorized work and checks.
- [Review](references/review.md): independent review, repair boundaries, evidence.
- [Delivery](references/delivery.md): branch/PR offer and acceptance boundary.
- [Readiness](references/readiness.md): only when the installed method requires it.
- [Governance](references/governance.md): decision cards and exact command bundles
  when a gate/approval needs explanation. Do not preload for routine execution.

## Human visibility is not agent context

For an exact Work, `aisdlc observe --swarm <swarm> --work <work> --json` returns a
compact read-only snapshot. A human/host can separately run `aisdlc observe --watch
--swarm <swarm> --work <work> --detail detailed --ui-file <new-file>` and inspect
that file. Do not feed the activity stream, heartbeats or repeated full snapshots
back into the conversation. Never run a polling conversation just to narrate wait.

Normal/detailed/diagnostic human views are rendered locally, not by a model.
Their verbosity does not change the machine snapshot or phase instructions.
`stderr` alone is not isolation: hosts capturing both streams must use the separate
UI file/channel. Observer heartbeats indicate the observer is alive, not that an
external agent is active. Usage without a reported basis stays unknown; never
claim missing usage is zero. Secrets and arbitrary PII cannot be made safe merely
by calling them diagnostics; raw process output is excluded.

## Anticipate without crossing boundaries

Explain what is happening, what was verified, what needs a human decision and
what is next. Prepare the next step within current authority. Do not invent live
activity, percentages, approval or completion. The current Start prepares a
handoff but does not launch the executor: report that honestly. Phase guidance is
portable behavior, not a claim that every host implements an enforced agent loop.

`aisdlc continue --json` exposes the existing guided projection; use explicit
`--swarm` and `--work`. Stop if its identity differs from this iteration. Exact
commands are available with `continue --commands`, details with `--expert`.
