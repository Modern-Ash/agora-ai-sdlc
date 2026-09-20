---
schema: "agora/role/v1"
id: "operator"
required-capabilities: ["operations"]
allowed-actor-kinds: ["human", "ai-agent"]
allowed-actions: ["work.transition", "criterion.satisfy", "work.clarify", "artifact.add", "evidence.add", "checklist.add", "checklist.check", "handoff.create"]
allowed-tool-capabilities: ["repository.read", "docs.read", "ci.read"]
allowed-environments: ["*"]
---

# Operator

**Accountable for:** deployment and operational evidence.
**Authority:** marks criteria deployed; may send failed operations back to construction. Deploy or release needs an explicit project environment grant; never implied.
**Delegation:** AI execution only within the granted environment.
