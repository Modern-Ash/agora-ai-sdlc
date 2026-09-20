---
schema: "agora/gate/v1"
id: "rework-recorded"
require-all-criteria: false
require-required-artifacts: true
required-artifacts: ["rework-record"]
require-successful-evidence: false
required-approval-roles: []
require-resolved-clarifications: false
---

# rework-recorded

Rework cannot proceed until a `rework-record` artifact is registered. The record states the reason and lists the affected artifacts (see docs/method/lifecycle.md).
