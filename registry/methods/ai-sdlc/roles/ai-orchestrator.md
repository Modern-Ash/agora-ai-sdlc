---
schema: "agora/role/v1"
id: "ai-orchestrator"
required-capabilities: ["orchestration"]
allowed-actor-kinds: ["ai-agent", "swarm"]
allowed-actions: ["swarm.assign", "work.decompose", "work.delegate", "work.block", "handoff.create", "work.clarify", "artifact.add"]
allowed-tool-capabilities: ["repository.read", "docs.read"]
allowed-environments: ["*"]
---

# AI Orchestrator

**Accountable for:** coordination of AI execution: splitting work, delegating and blocking.
**Authority:** none over approvals, gates or lifecycle transitions.
**Accountability:** always operates on behalf of a human role-holder; it is an execution role, not an accountability role.
