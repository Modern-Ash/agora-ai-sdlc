---
schema: "agora/role/v1"
id: "builder"
required-capabilities: ["implementation"]
allowed-actor-kinds: ["human", "ai-agent","swarm"]
allowed-actions: ["work.transition", "criterion.satisfy", "work.clarify", "artifact.add", "evidence.add", "usage.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "repository.write", "docs.read", "docs.write", "ci.read"]
allowed-environments: ["*"]
---

# Builder

**Accountable for:** implementation and build evidence.
**Authority:** marks criteria built; may send operations failures back to construction.
**Cannot:** approve gates (never sole approver of its own critical output), merge, release or deploy.
**Delegation:** usually an AI actor; the accountable human is recorded in the assignment.
