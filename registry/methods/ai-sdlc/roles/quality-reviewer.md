---
schema: "agora/role/v1"
id: "quality-reviewer"
required-capabilities: ["review"]
allowed-actor-kinds: ["human", "ai-agent"]
allowed-actions: ["work.transition", "criterion.satisfy", "approval.add", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "docs.read", "review.read", "review.write", "ci.read"]
allowed-environments: ["*"]
---

# Quality Reviewer

**Accountable for:** independent verification of construction output.
**Authority:** verifies criteria; approves the build gate; advances construction to operations.
**Independence:** must not be the actor that produced the reviewed output (enforced by policy profiles, issue #22).
**Delegation:** AI review allowed; the accountable human stays recorded.
