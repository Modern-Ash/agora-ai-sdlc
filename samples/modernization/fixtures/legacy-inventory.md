---
schema: agora-ai-sdlc/artifact/v1
kind: legacy-inventory
version: 1
id: LGI-001
work: feature
revision: 1
traces-to: []
separation-policy: [distinct-actor]
required-sections: [System boundary, Components and ownership, Data and interfaces, Runtime and deployment, Unknowns]
---
# Legacy inventory
## System boundary
Checkout total calculation.
## Components and ownership
One legacy checkout module owned by the payments team.
## Data and interfaces
Cart lines enter; a monetary total leaves.
## Runtime and deployment
Runtime details are observed only in the fixture environment.
## Unknowns
Rounding for an empty cart is not observable from retained cases.

