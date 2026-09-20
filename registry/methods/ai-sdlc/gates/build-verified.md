---
schema: "agora/gate/v1"
id: "build-verified"
require-all-criteria: true
required-criterion-stage: "verified"
require-required-artifacts: true
required-artifacts: ["implementation-plan", "test-strategy"]
require-successful-evidence: true
required-evidence-types: ["test-suite"]
required-approval-roles: ["quality-reviewer"]
require-resolved-clarifications: false
---

# build-verified

Operations cannot begin until an `implementation-plan` and a `test-strategy` artifact are registered, every criterion is `verified`, a successful `test-suite` evidence record exists in the current revision, and the Quality Reviewer approves. Failed or absent test evidence blocks. A later successful record supersedes an earlier failure, so record failures too: the history stays auditable.
