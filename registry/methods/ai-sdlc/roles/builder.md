---
schema: "agora/role/v1"
id: "builder"
required-capabilities: ["implementation"]
allowed-actor-kinds: ["human", "ai-agent", "swarm"]
allowed-actions: ["criterion.satisfy", "work.transition", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "approval.add", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "repository.write", "docs.read", "docs.write", "ci.read"]
allowed-environments: ["*"]
---

# Builder

Owns construction: implements units of work and records build and verification evidence. Has no merge, release or deploy authority.
