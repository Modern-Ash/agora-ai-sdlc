---
schema: "agora-ai-sdlc/artifact/v1"
kind: "configuration-delta"
version: 1
id: "CFD-001"
work: "payments-change"
revision: 1
traces-to: ["CHP-001"]
change-plan: "CHP-001"
changes:
  - key: "billing.schedule.enabled"
    before: "false"
    after: "true"
    resource: "payments-api/config/application.yaml"
release-evidence: ["evidence:release/payments-2026.09.21"]
rollback-linkage: ["repo://ops/rollback/recurring-payments.md"]
required-sections: ["Delta", "Release evidence", "Rollback linkage"]
---
# Configuration delta

## Delta

Enable recurring billing schedule.

## Release evidence

Release evidence is referenced.

## Rollback linkage

Rollback procedure is linked.
