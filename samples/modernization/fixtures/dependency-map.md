---
schema: agora-ai-sdlc/artifact/v1
kind: dependency-map
version: 1
id: DPM-001
work: feature
revision: 1
traces-to: [LGI-001]
separation-policy: [distinct-actor]
required-sections: [Nodes, Edges, External dependencies, Cycles and coupling, Unknown relationships]
---
# Dependency map
## Nodes
Checkout and tax lookup.
## Edges
Checkout calls tax lookup synchronously.
## External dependencies
Tax lookup remains outside the slice.
## Cycles and coupling
No observed cycle.
## Unknown relationships
No additional caller was inferred.

