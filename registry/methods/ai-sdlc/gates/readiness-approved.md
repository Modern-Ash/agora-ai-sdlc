---
schema: "agora/gate/v1"
id: "readiness-approved"
require-all-criteria: false
require-required-artifacts: true
required-artifacts: ["readiness-assessment"]
require-successful-evidence: false
required-approval-roles: ["product-owner"]
require-resolved-clarifications: true
---

# readiness-approved

Intent work cannot begin until a `readiness-assessment` artifact is registered, every clarification affecting the current inputs is resolved, and the Product Owner has approved. Evidence obligations are none in the base gate; profiles may add them (issue #20).
