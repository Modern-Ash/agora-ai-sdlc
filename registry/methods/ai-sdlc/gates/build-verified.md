---
schema: "agora/gate/v1"
id: "build-verified"
require-all-criteria: true
required-criterion-stage: "verified"
require-required-artifacts: true
required-artifacts: ["domain-model", "logical-design", "implementation-plan", "test-strategy", "deployment-unit"]
require-successful-evidence: true
required-evidence-types: ["test-suite"]
required-approval-roles: ["quality-reviewer"]
require-resolved-clarifications: false
---

# build-verified

Operations cannot begin until Domain Design (`domain-model`), Logical Design, an `implementation-plan`, a `test-strategy`, and a `deployment-unit` are registered, every criterion is `verified`, a successful `test-suite` evidence record exists in the current revision, and the Quality Reviewer approves. Failed or absent test evidence blocks. A later successful record supersedes an earlier failure, so record failures too: the history stays auditable.
