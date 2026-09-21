---
schema: "agora/role/v1"
id: "product-owner"
required-capabilities: ["specification"]
allowed-actor-kinds: ["human", "ai-agent"]
allowed-actions: ["work.create", "work.decompose", "work.transition", "work.reopen", "criterion.satisfy", "approval.add", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "repository.governance.read", "issue.read", "docs.read", "docs.write"]
allowed-environments: ["*"]
---

# Product Owner

**Accountable for:** intent, scope and acceptance.
**Authority:** approves intent, design and completion; advances readiness, intent and completion; accepts criteria; reopens completed work as a new revision.
**Delegation:** an AI actor may execute this role only under an accountable human role-holder recorded in the swarm assignment; the human stays accountable.
**Cannot:** build, deploy or waive gates.
