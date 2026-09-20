---
schema: "agora/role/v1"
id: "domain-expert"
required-capabilities: ["specification"]
allowed-actor-kinds: ["human", "ai-agent"]
allowed-actions: ["work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "docs.read", "docs.write"]
allowed-environments: ["*"]
---

# Domain Expert

**Accountable for:** correctness of domain knowledge supplied to intent and design.
**Authority:** advisory only: answers clarifications and contributes artifacts. No transitions and no approvals.
**Delegation:** an AI actor may draft; a human domain expert confirms critical domain claims.
