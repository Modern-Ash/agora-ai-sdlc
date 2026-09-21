# Bolts

A **Bolt** is a short iteration over one Unit of Work. A `bolt-plan` artifact (`BLP-NNN`, template `templates/bolt-plan.md`) records every Bolt for a Unit. The AI proposes the plan; an accountable human approves the exact revision before any Bolt runs.

## Bolt fields

| Field | Meaning |
|---|---|
| `id` | lowercase slug, unique in the plan |
| `mode` | `sequential` or `parallel` |
| `status` | `proposed`, `approved`, `running`, `completed`, `failed` |
| `tasks` | non-empty list of tasks/stories |
| `depends-on` | earlier Bolt ids only (so cycles are impossible) |
| `writes` | paths the Bolt may change; the basis for conflict detection |
| `produces` | ids of artifacts the Bolt delivers |
| `evidence` | evidence links; required once `completed` |

Plan-level fields: `unit` (`UOW-NNN`, must be in `traces-to`), optional `plan` (`PLN-NNN`), `proposed-by`, `approval-state`, `approved-by`, `approved-revision`.

## Rules

- **Approval:** until the plan is `approved` at its current revision, every Bolt must be `proposed`. Editing the plan invalidates approval (`bolt.approval_stale`).
- **Lifecycle:** `proposed -> approved -> running -> completed | failed`. `failed` and `completed` are terminal for the Bolt.
- **Dependencies:** a `running` or `completed` Bolt requires all its dependencies `completed`.
- **Sequential vs parallel:** a `sequential` Bolt must depend, directly or transitively, on every earlier Bolt. Bolts without a dependency path between them may run concurrently.
- **Conflicts:** two Bolts with no dependency path must not write overlapping paths (equal, or one a parent directory of the other). Otherwise `bolt.parallel_conflict`.
- **Evidence:** a `completed` Bolt needs evidence links. `construction_evidence_complete` is true only when every Bolt is `completed`; it is input to the Construction gate, not a substitute for it.

## Traceability

Generic traceability accepts `bolt-plan` traced to `unit-of-work` (and `plan`). `agora_ai_sdlc.bolts.trace` returns Unit -> Bolt -> produced artifacts/evidence.

## CLI

```
agora-ai-sdlc bolt-validate PATH [--json]
```

Read-only: validates the plan and prints the trace and the Bolts ready to start (more than one ready Bolt means they can run in parallel). It exits 2 with a stable `bolt.*` code on failure. It does not run Bolts, call an LLM, or touch a repository; `assert_can_start` and `check_transition` are the fail-closed checks an executor must call.

Sample: `tests/fixtures/bolts/parallel.md` (`api` and `ui` in parallel).
