# Level 1 and Level-N planning

Agora AI-SDLC represents AI-proposed execution plans as durable `plan` artifacts. Plans use the shared `agora-ai-sdlc/artifact/v1` envelope for identity, revision and traceability, plus plan-specific fields validated by `agora_ai_sdlc.plans`.

## Contract

A plan records:

- `id`: `PLN-NNN`;
- `level`: positive integer;
- `parent-plan`: null at Level 1, required above Level 1;
- `intent`: required `INT-NNN` scope;
- `unit`: optional `UOW-NNN` scope;
- `proposed-by`: actor that proposed the plan;
- `approval-state`: `pending`, `approved`, or `rejected`;
- `approved-by`: accountable approver when approved;
- `approved-revision`: exact artifact revision approved;
- ordered `steps`.

Each step contains an id, `execute` or `skip` decision, rationale, dependencies on earlier steps, and required/produced artifact kinds.

## Recursive decomposition

Level 1 has no parent. Every Level N plan above Level 1:

1. names its parent in `parent-plan`;
2. includes that `PLN-NNN` in `traces-to`;
3. has level exactly parent level + 1;
4. preserves the parent's Intent and Unit scope.

The graph validator rejects missing parents, invalid level jumps, scope changes and duplicate plan ids.

## Approval and revision safety

Plan execution fails closed until the exact current revision is approved.

An approved plan must record both `approved-by` and `approved-revision`. If an approved artifact changes from revision 1 to revision 2 while retaining approval for revision 1, parsing fails with `plan.approval_stale`. The revised plan must be reviewed and approved again.

`assert_executable(plan)` is the explicit flavor boundary used by later adaptive-execution work. This issue does not automatically execute plan steps; adaptive pathway selection is #100 and Bolt execution is #101.

## Traceability

Plan scope references must also appear in `traces-to`:

- Intent is always traced.
- Unit is traced when present.
- Parent plan is traced for Level N > 1.

The generic artifact graph therefore retains backward/forward links while plan-specific validation enforces recursive semantics.

## Example

```yaml
kind: plan
id: PLN-002
revision: 1
traces-to: [INT-001, UOW-001, PLN-001]
level: 2
parent-plan: PLN-001
intent: INT-001
unit: UOW-001
proposed-by: project:planner
approval-state: approved
approved-by: project:po
approved-revision: 1
steps:
  - id: logical-design
    decision: execute
    rationale: Detail the approved construction step.
    dependencies: []
    required-artifacts: [requirements]
    produced-artifacts: [logical-design]
```

All validation is local, deterministic and provider-neutral.


## Adaptive pathway policy

Plan structure and approval are independent from pathway policy. After a Plan is approved, the adaptive validator can check it against a checked-in pathway and effective depth without introducing pathway-specific lifecycle states.

See [adaptive pathway planning](adaptive-planning.md).
