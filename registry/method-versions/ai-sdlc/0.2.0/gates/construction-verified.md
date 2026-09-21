---
schema: "agora/gate/v1"
id: "construction-verified"
require-all-criteria: true
required-criterion-stage: "verified"
require-required-artifacts: true
required-artifacts: ["domain-model", "architecture", "implementation-plan", "test-strategy"]
require-successful-evidence: true
required-evidence-types: ["test-suite"]
required-approval-roles: ["developer"]
require-resolved-clarifications: false
---

# construction-verified

Operations starts after the technical design and implementation/test artifacts exist, criteria are verified, successful test-suite evidence is recorded and the Developer approves the construction result.
