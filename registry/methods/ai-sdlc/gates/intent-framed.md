---
schema: "agora/gate/v1"
id: "intent-framed"
require-all-criteria: true
required-criterion-stage: "elaborated"
require-required-artifacts: true
required-artifacts: ["intent"]
require-successful-evidence: false
required-approval-roles: ["product-owner"]
require-resolved-clarifications: true
---

# intent-framed

Inception cannot begin until the `intent` artifact is registered, every criterion is `elaborated`, clarifications are resolved and the Product Owner approves. Human ownership of intent is not removable by any profile.
