---
schema: "agora/role/v1"
id: "security-reviewer"
required-capabilities: ["security-review"]
allowed-actor-kinds: ["human", "ai-agent"]
allowed-actions: ["criterion.satisfy", "approval.add", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "docs.read", "review.read", "review.write"]
allowed-environments: ["*"]
---

# Security Reviewer

**Accountable for:** security findings and risk acceptance recommendations.
**Authority:** contributes evidence and approvals where a profile requires a security gate. No transitions.
**Independence:** must be independent from the producer of the reviewed change.
