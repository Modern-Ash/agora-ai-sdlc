---
sources: [issues #4, #6, #27-#31, #36]
status: draft
---
# Integration contracts

- Profiles use provider-neutral Tool Pack operations; provider translation is bounded and reviewable.
- External systems stay operational sources; Agora stores normalized facts, evidence and references.
- Write operations are opt-in and policy-controlled; no credentials stored.
- Contract tests run without live accounts; live smoke tests need explicit non-production confirmation.
- External failure must be distinguishable from Agora policy denial.
- MVP priority: GitHub and generic CI evidence.
- Studio consumes versioned application-service JSON only: no Method Pack/flavor Markdown parsing, direct `.agora/` access or browser-supplied filesystem paths.
- Read projections keep unknown lifecycle ids generic and represent missing sections explicitly as unavailable with a safe reason.
