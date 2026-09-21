# AI-SDLC 0.2.0 protocol

The operating pattern remains: **plan -> clarify -> human decision -> execute -> validate**.

## Phases

| Phase | Base roles | Purpose |
| --- | --- | --- |
| inception | product-owner, developer | frame Intent, elaborate requirements, Units and design inputs, then approve construction |
| construction | developer | design, implement and verify the approved work |
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

## Deferred capabilities

First-class recursive plans, adaptive pathway selection and executable Bolt plans are not claimed by 0.2.0 itself. They are provided by the flavor (issues #99, #100 and #101; see `docs/method/bolts.md`).
