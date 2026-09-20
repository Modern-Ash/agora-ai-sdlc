# AI-SDLC protocol

## Operating pattern

Every phase repeats: **plan -> clarify -> human decision -> execute -> validate**. The AI drafts a plan from current inputs, raises targeted clarifications, the accountable human decides, the AI executes the decision, and results are validated against evidence. Ambiguity is resolved before execution; no phase advances without its gate.

## Phases

| Phase | Responsible roles | Required outputs | Stops when |
|---|---|---|---|
| readiness | product-owner | `readiness-brief` artifact; clarifications resolved | Gate `readiness-cleared` passes, or a clarification remains open |
| intent | product-owner, architect | `intent` artifact; criteria elaborated | Gate `intent-approved` passes, or the Product Owner withholds approval |
| inception | architect | `architecture`, `domain-model`; criteria designed | Gate `design-approved` passes, or a requirements gap sends work back to `intent` |
| construction | builder, quality-reviewer | Built and verified criteria; successful evidence | Gate `build-verified` passes, or a design gap sends work back to `inception` |
| operations | operator, product-owner | Deployment evidence; criteria deployed then accepted | Gate `completion` passes, or a failure sends work back to `construction` |
| completed | product-owner | Accepted work revision | Terminal; further change opens a new revision |

## Unit of Work and bolt

A **Unit of Work** is a bounded slice of the intent, delivered independently and traced to acceptance criteria. A **bolt** is a short, focused iteration over a Unit of Work inside one phase. Bolts carry no time tracking in Core: they are a working convention recorded in evidence, not a lifecycle state.

## Rules

- Fail closed: missing evidence, unresolved clarification or missing approval blocks the transition.
- Critical artifacts receive independent review.
- Rework is explicit, traceable and uses a defined transition.
- Only provider-neutral capabilities are referenced.
