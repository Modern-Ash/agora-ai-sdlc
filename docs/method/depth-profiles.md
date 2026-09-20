# Depth profiles

Depth sets how many obligations each gate carries. Data: [profiles/depth/](../../profiles/depth/). Code: `agora_ai_sdlc.depth_profiles`. Inspect with `agora-ai-sdlc profile [depth]` (JSON).

| Depth | Definition |
|---|---|
| minimal | `standard` minus explicit, justified optional obligations: at `completion`, the `operational-readiness` artifact and `security-scan` evidence |
| **standard** (default) | Exactly the Method Pack gates, which is what Agora Core enforces |
| comprehensive | standard plus `domain-model` and `threat-model` at `architecture-approved`, `security-reviewer` approval at `build-verified`, `learning-record` at `completion` |
| regulated | comprehensive plus `governance-owner` approval at `intent-framed` and `completion`; requires signed actions and human final approval |

## Rules

- **Deterministic:** resolution reads the pack gates plus the profile chain (`extends`); same inputs, same snapshot (golden snapshots in `tests/fixtures/depth`).
- **Monotonic:** each depth's obligations contain its parent's. Only `minimal` removes obligations, must state a justification, and can never remove the Product Owner's approval of intent.
- **Fail early:** unknown or invalid profiles raise `profile.unknown`/`profile.invalid` before anything is read or written; resolution never touches work state.
- **Regulated:** `requires: signed-actions, human-final-approval` are declared and surfaced by assessment; verification depends on Core's signed-action support and is not checked offline.

## Choosing a depth

`recommend(risk, reversibility, data_sensitivity, operational_impact)` returns: `regulated` for regulated data; otherwise the highest of the factors: everything low/reversible/public-or-internal gives `minimal`; a medium factor or hard-to-reverse change gives `standard`; high risk or impact, irreversible change or confidential data gives `comprehensive`. It is a recommendation; the accountable Product Owner decides.

## Changing depth on in-progress work

`assess(depth, gate, artifacts, evidence, approvals)` is read-only and lists the obligations of a gate not yet met. Moving to a stricter depth therefore exposes gaps (for example a missing `threat-model`) without altering the work item; nothing already recorded is removed. Moving to a lighter depth never invalidates recorded evidence. Changes should be recorded as a decision by the Product Owner.

## Limits

Agora Core 0.8.2 enforces one fixed gate set per Method Pack, so only `standard` is enforced by Core. Other depths are resolved and assessed here but are advisory until Core supports profile-aware gates or a per-depth pack variant is generated (not implemented). Where the depth is stored for a work item is not yet defined.
