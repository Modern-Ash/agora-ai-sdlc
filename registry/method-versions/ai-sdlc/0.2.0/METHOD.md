---
schema: "agora/method/v1"
id: "ai-sdlc"
name: "AI-SDLC"
version: "0.2.0"
dependencies: []
required-roles: ["product-owner", "developer"]
optional-roles: ["quality-reviewer"]
work-states: ["inception", "construction", "operations", "completed"]
criterion-stages: ["elaborated", "designed", "built", "verified", "deployed", "accepted"]
criterion-stage-roles: {"elaborated":["product-owner","developer"],"designed":["developer"],"built":["developer"],"verified":["developer"],"deployed":["developer"],"accepted":["product-owner"]}
terminal-state: "completed"
wip-limits: {}
---

# AI-SDLC Method Pack 0.2.0

Provider-neutral three-phase candidate lifecycle:

`inception -> construction -> operations -> completed`.

`completed` is Agora's terminal recording state, not an additional delivery phase.

Readiness and Intent remain flavor artifacts/capabilities used during Inception; they are not lifecycle states in this version.

The base method requires only Product Owner and Developer. Quality Reviewer is an optional participant for teams or profiles that require independent review.
