# Issue lifecycle

| State | Entry | Exit |
|---|---|---|
| `backlog` | Issue created | Dependencies and scope reviewed |
| `blocked` | Open dependency or pending decision documented | Blocker resolved -> `backlog` or `ready` |
| `ready` | Meets the readiness checklist below | Agent picks it up -> `planning` |
| `planning` | `TASK.md` being created; clarifications raised | `TASK.md` complete, clarifications closed -> `implementing`; too large -> split, back to `backlog` |
| `implementing` | Approved `TASK.md` | `TESTS.md`, `RESULT.md` complete -> `review` |
| `review` | Independent reviewer assigned | Verdict `approved*` -> `verified`; `changes-requested` -> `changes-requested` |
| `changes-requested` | Review findings recorded | Fixes and new evidence -> `implementing` |
| `verified` | Criteria verified, PR ready | PR merged by a human and issue closed -> `done` |
| `done` | Merged and closed | Terminal |

## Ready checklist

- Dependencies resolved.
- Scope defined; allowed paths identified.
- Acceptance criteria verifiable.
- No open architectural decision.
- Reasonable context budget ([token-efficiency](token-efficiency.md)).

Labels `agent:*` mirror these states (`agent:ready`, `agent:blocked`, `agent:planning`, `agent:implementing`, `agent:review`).
