---
schema: "agora/gate/v1"
id: "completion"
require-all-criteria: true
required-criterion-stage: "accepted"
require-required-artifacts: true
required-artifacts: ["deployment-plan", "rollback-procedure", "operational-readiness"]
require-successful-evidence: true
required-evidence-types: ["deployment", "security-scan"]
required-approval-roles: ["product-owner"]
require-resolved-clarifications: false
---

# completion

Completion requires `deployment-plan`, `rollback-procedure` and `operational-readiness` artifacts, every criterion `accepted`, successful `deployment` and `security-scan` evidence in the current revision, and Product Owner approval, which records explicit acceptance and the accountable actor. `operational-readiness` is folded into this gate (three gates in issue #18 map to two transitions). A `security-scan` success is recorded only when no blocking findings remain open; profiles decide what severity blocks (issue #20).
