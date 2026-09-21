---
schema: "agora/method/v1"
id: "ai-sdlc"
name: "AI-SDLC"
version: "0.1.1"
dependencies: []
required-roles: ["product-owner", "architect", "builder", "operator", "quality-reviewer"]
work-states: ["readiness", "intent", "inception", "construction", "operations", "completed"]
criterion-stages: ["elaborated", "designed", "built", "verified", "deployed", "accepted"]
criterion-stage-roles: {"elaborated":["product-owner","architect"],"designed":["architect"],"built":["builder"],"verified":["quality-reviewer","builder"],"deployed":["operator"],"accepted":["product-owner"]}
terminal-state: "completed"
wip-limits: {}
---

# AI-SDLC Method Pack

Vendor-neutral, AI-first delivery lifecycle: AI plans, asks and executes; accountable humans keep every critical decision. No runtime, provider or model is assumed; roles are held by human, AI or service actors.

Lifecycle: `readiness -> intent -> inception -> construction -> operations -> completed`.

`readiness` is the initial state (first in `work-states`); `completed` is terminal for a work revision.

## Gates

- **readiness-approved** (readiness to intent): a `readiness-assessment` artifact is registered, no clarification is open, and the Product Owner has approved.
- **intent-framed** (intent to inception): an `intent` artifact is registered, every criterion has reached `elaborated`, and the Product Owner has approved.
- **architecture-approved** (inception to construction): `requirements` and `architecture` artifacts are registered, every criterion has reached `designed`, and the Architect and Product Owner have approved.
- **build-verified** (construction to operations): every criterion has reached `verified`, successful evidence exists, and the Quality Reviewer has approved.
- **completion** (operations to completed): every criterion has reached `accepted`, deployment evidence exists, and the Product Owner has approved.

## Rework

- `inception -> intent`: intent or scope proves insufficient.
- `construction -> inception`: a design or requirements gap surfaces.
- `operations -> construction`: verification or deployment fails.

Rework reuses an earlier state and preserves history. Changes after `completed` create a new work revision; accepted history is never mutated.
