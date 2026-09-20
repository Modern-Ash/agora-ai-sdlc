# AI-SDLC lifecycle

States: `readiness -> intent -> inception -> construction -> operations -> completed`. Definitions live in [registry/methods/ai-sdlc/transitions](../../registry/methods/ai-sdlc/transitions) and [gates](../../registry/methods/ai-sdlc/gates).

| Transition | Roles | Gate |
|---|---|---|
| readiness -> intent | product-owner | readiness-cleared |
| intent -> inception | product-owner, architect | intent-approved |
| inception -> construction | architect | design-approved |
| construction -> operations | quality-reviewer | build-verified |
| operations -> completed | product-owner | completion |
| inception -> intent (rework) | architect, product-owner | rework-recorded |
| construction -> inception (rework) | architect | rework-recorded |
| operations -> construction (rework) | builder, operator | rework-recorded |

## Retry, rework, new revision

- **Retry:** a gate rejected the move; state does not change. Fix the missing item and try again. Core never moves state on a rejected gate.
- **Rework:** an earlier phase must be revisited within the same revision. Requires a `rework-record` artifact. Earlier artifacts and evidence are kept.
- **New revision:** completed work is never mutated. The product-owner reopens it with a reason (`work reopen`); Core opens a new revision, closes the previous one intact, and resets criteria/artifacts/evidence for the new revision, starting from `operations`.

## Rework record

Register a `rework-record` artifact containing: **reason**, **affected artifacts** (paths or ids) and the **requester**. The gate enforces that the artifact exists; the content is a convention, since Core gates cannot inspect artifact content.

## Known limitations

- A `rework-record` registered once satisfies the gate for later reworks in the same revision; Core gates check artifact kind presence, not freshness. Register a distinct record and review it at each rework.
- The reason and affected-artifact fields are not machine-validated (see above).
- Who performed a transition and when is recorded by Core; verified only through the outcomes tested, not by reconstructing history from records.
