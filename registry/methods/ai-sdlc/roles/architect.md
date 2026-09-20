---
schema: "agora/role/v1"
id: "architect"
required-capabilities: ["specification"]
allowed-actor-kinds: ["human", "ai-agent", "swarm"]
allowed-actions: ["swarm.assign", "work.decompose", "work.verify-consistency", "work.gherkin", "criterion.satisfy", "work.transition", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "approval.add", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "repository.governance.read", "docs.read", "docs.write", "review.read"]
allowed-environments: ["*"]
---

# Architect

Owns inception: turns intent into design and domain model, and returns work to intent or accepts it back from construction when a gap surfaces.
