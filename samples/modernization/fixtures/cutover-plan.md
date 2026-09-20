---
schema: agora-ai-sdlc/artifact/v1
kind: cutover-plan
version: 1
id: CUT-001
work: feature
revision: 1
traces-to: [MGP-001, EQV-002]
slice-ids: [checkout-total]
separation-policy: [distinct-actor, human-final]
required-sections: [Scope and prerequisites, Sequence, Traffic and data, Verification, Abort and rollback]
---
# Cutover plan
## Scope and prerequisites
Checkout-total with passing EQV-002.
## Sequence
Enable shadow, verify, then route traffic.
## Traffic and data
No persistent data transfer.
## Verification
Compare totals and operational signals.
## Abort and rollback
Return routing to the legacy calculator.

