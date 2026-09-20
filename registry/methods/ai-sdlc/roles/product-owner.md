---
schema: "agora/role/v1"
id: "product-owner"
required-capabilities: ["specification"]
allowed-actor-kinds: ["human", "ai-agent", "swarm"]
allowed-actions: ["swarm.assign", "work.decompose", "criterion.satisfy", "work.transition", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "approval.add", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "repository.governance.read", "docs.read", "docs.write"]
allowed-environments: ["*"]
---

# Product Owner

Accountable for intent, scope and acceptance. Approves intent, design and completion; may be a human, or an AI actor delegated by an accountable human.
