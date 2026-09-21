---
schema: "agora/role/v1"
id: "quality-reviewer"
required-capabilities: ["review"]
allowed-actor-kinds: ["human", "ai-agent"]
allowed-actions: ["criterion.satisfy", "approval.add", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "docs.read", "review.read", "review.write", "ci.read"]
allowed-environments: ["*"]
---

# Quality Reviewer

Optional independent verification participant. Adoption/depth profiles decide when independent review is mandatory.
