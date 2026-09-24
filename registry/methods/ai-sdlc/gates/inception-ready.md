---
schema: "agora/gate/v1"
id: "inception-ready"
require-all-criteria: true
required-criterion-stage: "elaborated"
require-required-artifacts: true
required-artifacts: ["requirements", "user-stories", "nfr", "risk-register", "measurement-criteria", "plan", "unit-of-work", "bolt-plan"]
require-successful-evidence: false
required-approval-roles: ["architect", "product-owner"]
require-resolved-clarifications: true
---

# inception-ready

Construction cannot begin until the Intent has been progressively enriched into the core AI-DLC
Inception contract: requirements/User Stories, explicit NFRs and risks, Measurement Criteria, an
approved Level 1 Plan, cohesive Units and suggested Bolts. Clarifications must be resolved and the
responsible Product Owner and architecture/developer authority must validate the proposal.

PRFAQ remains optional because the method treats it as an optional Inception output.

Domain Design and Logical Design are intentionally not required here: they are Construction activities.
