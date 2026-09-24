# AI-SDLC 0.2.0 protocol

The operating pattern remains: **plan -> clarify -> human decision -> execute -> validate**.

## Phases

| Phase | Base roles | Purpose |
| --- | --- | --- |
| inception | product-owner, developer | clarify Intent; validate Level 1 Plan, Stories/criteria, NFRs, risks, Measurement Criteria, Units and suggested Bolts |
| construction | developer | Domain Design -> Logical Design -> implementation/tests -> Deployment Unit, with brownfield semantic elevation first when needed |
| operations | developer, product-owner | deploy, observe, remediate through governed decisions and accept the revision |
| completed | product-owner | terminal Agora record of accepted work |

## Forward gates

- `inception-approved`: Inception to Construction.
- `construction-verified`: Construction to Operations.
- `completion`: Operations to completed.

## Rework

- `construction -> inception`
- `operations -> construction`

Rework transitions are deliberately ungated in this candidate pack. Core records the transition history durably; higher-assurance profiles may add evidence/policy obligations outside the base method.

## Flavor capabilities used by this pack\n\nThe method gate requires Level 1 `plan` and `bolt-plan` artifact kinds. Recursive plan validation, adaptive pathway selection, executable Bolt semantics, Context Graph traceability and the continuous wizard are implemented by the AI-SDLC flavor around this Core Method Pack. They enrich execution without changing the three canonical phase names.
