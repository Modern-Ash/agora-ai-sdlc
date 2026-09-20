---
schema: "agora/role/v1"
id: "architect"
required-capabilities: ["specification"]
allowed-actor-kinds: ["human", "ai-agent","swarm"]
allowed-actions: ["work.decompose", "work.verify-consistency", "work.gherkin", "work.transition", "criterion.satisfy", "approval.add", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "repository.governance.read", "docs.read", "docs.write", "review.read"]
allowed-environments: ["*"]
---

# Architect

**Accountable for:** inception design and domain model.
**Authority:** approves design; advances inception to construction; returns work to intent or from construction to inception when a gap surfaces; marks criteria designed.
**Delegation:** AI execution allowed; design approval remains with the accountable architect.
