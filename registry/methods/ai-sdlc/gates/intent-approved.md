---
schema: "agora/gate/v1"
id: "intent-approved"
require-all-criteria: true
required-criterion-stage: "elaborated"
require-required-artifacts: true
required-artifacts: ["intent"]
require-successful-evidence: false
required-approval-roles: ["product-owner"]
require-resolved-clarifications: false
---

# intent-approved

Inception cannot begin until the intent is registered, every criterion is elaborated and the Product Owner approves.
