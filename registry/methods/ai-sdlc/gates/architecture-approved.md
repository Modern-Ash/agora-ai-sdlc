---
schema: "agora/gate/v1"
id: "architecture-approved"
require-all-criteria: true
required-criterion-stage: "designed"
require-required-artifacts: true
required-artifacts: ["requirements", "architecture"]
require-successful-evidence: false
required-approval-roles: ["architect", "product-owner"]
require-resolved-clarifications: true
---

# architecture-approved

Construction cannot begin until `requirements` and `architecture` are registered in the current work revision, every criterion is `designed`, clarifications are resolved, and both the Architect and the Product Owner approve. Requirements approval is folded into this gate: the Product Owner's approval covers the requirements (the four-gate split in issue #17 maps onto three transitions; see docs/method/lifecycle.md).
