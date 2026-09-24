---
schema: "agora/gate/v1"
id: "construction-verified"
require-all-criteria: true
required-criterion-stage: "verified"
require-required-artifacts: true
required-artifacts: ["domain-model", "logical-design", "implementation-plan", "test-strategy", "deployment-unit"]
require-successful-evidence: true
required-evidence-types: ["test-suite"]
required-approval-roles: ["developer"]
require-resolved-clarifications: false
---

# construction-verified

Operations starts after Domain Design, Logical Design, implementation/test artifacts and an operations-ready Deployment Unit exist; criteria are verified, successful test-suite evidence is recorded and the Developer approves the construction result. The broader architecture artifact remains supported by the flavor but is not a substitute for the AI-SDLC Domain Design -> Logical Design sequence.
