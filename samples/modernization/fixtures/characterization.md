---
schema: agora-ai-sdlc/artifact/v1
kind: characterization
version: 1
id: CHR-001
work: feature
revision: 1
traces-to: [LGI-001]
behaviors:
  - id: priced-cart
    status: known
    baseline: "two items total 2300 minor units"
    evidence: ["repo://fixtures/priced-cart.json"]
    reason: null
  - id: empty-cart-rounding
    status: unknown
    baseline: null
    evidence: []
    reason: "no retained observation exercises an empty cart"
separation-policy: [distinct-actor]
required-sections: [Observation boundary, Known behavior, Unknown behavior, Baseline method, Coverage limits]
---
# Behavior characterization
## Observation boundary
Fixture inputs against the retained legacy executable.
## Known behavior
Priced cart output is observed and evidenced.
## Unknown behavior
Empty-cart rounding is explicitly unknown.
## Baseline method
Compare normalized input and output documents.
## Coverage limits
No claim is made outside retained cases.

