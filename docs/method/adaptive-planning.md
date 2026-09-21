# Adaptive pathway planning

Agora AI-SDLC uses one Method Pack 0.2.0 lifecycle for every delivery pathway:

`inception -> construction -> operations -> completed`.

A pathway does not introduce a new state machine. It constrains an approved Level 1 / Level-N plan by declaring which method steps are mandatory, optional, or non-skippable for a delivery context.

## Pathways

The checked-in profiles under `profiles/pathways/` are:

- `trivial-change`
- `new-product`
- `brownfield`
- `refactor`
- `scaling`
- `regulated-change`

Each profile declares a minimum depth, mandatory steps, optional steps and explicit forbidden skips. The shared `policy.yaml` defines the closed step vocabulary, the common three-phase lifecycle, depth ordering and additional obligations introduced by stricter depth.

## AI proposes, Agora validates, humans approve

The AI may propose a Plan containing `execute` and `skip` decisions. Agora then validates the plan against the selected pathway and effective depth. The accountable human approves the exact Plan revision before it may be treated as executable.

A revised Plan invalidates the old approval through the first-class Plan rules from issue #99. The adaptive validator therefore does not authorize pending, rejected, or stale Plan revisions.

## Effective depth

Effective depth is the strictest of:

1. the pathway minimum;
2. an explicitly selected depth;
3. the active adoption profile depth.

Depth can only increase obligations. It can never make a pathway less strict than its declared minimum.

For example, a `trivial-change` Plan can omit non-mandatory design work at `minimal` or `standard`. If the Enterprise adoption profile is active, the effective depth becomes `comprehensive`, which promotes additional design, integration, security, and performance obligations.

The Regulated profile/depth promotes all comprehensive controls plus deployment-unit, rollback-readiness, and observability obligations. Attempts to skip those controls fail closed.

## Brown-field semantic elevation

The `brownfield` pathway requires:

- `brownfield-static-model`
- `brownfield-dynamic-model`

before construction-oriented work is authorized. These are pathway obligations, not extra lifecycle states.

Pass `--artifacts DIR` to `plan-validate` to enforce them: for any pathway whose policy makes both steps mandatory, the directory must hold a `static-system-model` (tracing to a `legacy-inventory`) and a `dynamic-system-model` (tracing to that static model) for the plan's `work`. Failures use `elevation.*` codes. See [context graph](context-graph.md).

## CLI

Validate an approved plan:

```bash
agora-ai-sdlc plan-validate plan.md --pathway trivial-change --depth standard
```

Use an adoption profile:

```bash
agora-ai-sdlc plan-validate plan.md --pathway regulated-change --profile regulated --json
```

The command is read-only. It does not execute plan steps, mutate a repository, call an LLM, or invoke a cloud/provider API. Successful validation means only that the current approved Plan revision is policy-authorized. Step execution is a separate capability; Bolt plans are validated by [bolts](bolts.md).

## Failure semantics

Validation fails closed when:

- the selected pathway is unknown;
- the plan contains unknown steps for that pathway;
- a mandatory step is missing;
- a mandatory/protected step is marked `skip`;
- a stricter depth/profile obligation is not satisfied;
- the Plan is not approved at its current revision;
- policy assets are malformed.

All errors use stable `pathway.*` codes.
