---
schema: "agora/role/v1"
id: "operator"
required-capabilities: ["operations"]
allowed-actor-kinds: ["human", "ai-agent", "swarm"]
allowed-actions: ["criterion.satisfy", "work.transition", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "approval.add", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "docs.read", "ci.read"]
allowed-environments: ["*"]
---

# Operator

Owns operations: deploys and records deployment evidence, only within an explicit environment grant.
