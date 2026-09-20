---
schema: "agora/role/v1"
id: "governance-owner"
required-capabilities: ["governance"]
allowed-actor-kinds: ["human"]
allowed-actions: ["gate.waive", "work.block", "work.cancel", "work.reopen", "approval.add", "work.clarify", "artifact.add", "evidence.add", "handoff.create"]
allowed-tool-capabilities: ["repository.governance.read", "docs.read"]
allowed-environments: ["*"]
---

# Governance Owner

**Accountable for:** exceptions and policy.
**Authority:** the only role that may waive a gate, cancel or reopen work; exceptions must be explicit and recorded.
**Human-only:** AI actors may not hold this role.
