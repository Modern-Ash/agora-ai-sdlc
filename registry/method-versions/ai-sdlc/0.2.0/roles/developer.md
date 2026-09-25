---
schema: "agora/role/v1"
id: "developer"
required-capabilities: ["implementation"]
allowed-actor-kinds: ["human", "ai-agent", "swarm"]
allowed-actions: ["work.transition", "criterion.satisfy", "approval.add", "work.clarify", "artifact.add", "evidence.add", "usage.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "repository.write", "docs.read", "docs.write", "ci.read", "review.read", "review.write"]
allowed-environments: ["*"]
---

# Developer

Accountable for technical elaboration, design, implementation, verification and operational delivery within the approved plan and policies.
