---
schema: "agora/role/v1"
id: "quality-reviewer"
required-capabilities: ["review"]
allowed-actor-kinds: ["human", "ai-agent", "swarm"]
allowed-actions: ["criterion.satisfy", "work.transition", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "approval.add", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "docs.read", "review.read", "review.write", "ci.read"]
allowed-environments: ["*"]
---

# Quality Reviewer

Independently verifies construction output against criteria and approves the build gate.
