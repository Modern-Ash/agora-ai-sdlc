---
schema: "agora/gate/v1"
id: "completion"
require-all-criteria: true
required-criterion-stage: "accepted"
require-required-artifacts: true
required-artifacts: ["operational-readiness", "rollback-procedure"]
require-successful-evidence: true
required-evidence-types: ["deployment", "security-scan"]
required-approval-roles: ["product-owner"]
require-resolved-clarifications: false
---

# completion

Completion requires accepted criteria, operational readiness and rollback artifacts, successful deployment/security evidence, and Product Owner acceptance.
