---
schema: "agora/role/v1"
id: "product-owner"
required-capabilities: ["specification"]
allowed-actor-kinds: ["human", "ai-agent"]
allowed-actions: ["work.create", "work.decompose", "work.transition", "work.reopen", "criterion.satisfy", "approval.add", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "repository.governance.read", "docs.read", "docs.write"]
allowed-environments: ["*"]
---

# Product Owner

Accountable for Intent, scope and final acceptance. Human accountability remains explicit even when an AI actor assists this role.
