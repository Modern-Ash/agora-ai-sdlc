---
schema: agora-ai-sdlc/artifact/v1
kind: equivalence-report
version: 1
id: EQV-002
work: feature
revision: 1
traces-to: [CHR-001, CNV-001, MGS-001]
slice-id: checkout-total
comparisons:
  - behavior: priced-cart
    result: equivalent
    evidence: ["repo://fixtures/priced-cart-passed.json"]
    explanation: null
    accepted-by: null
  - behavior: empty-cart-rounding
    result: accepted-difference
    evidence: ["repo://decisions/empty-cart.md"]
    explanation: "define empty cart total as zero because no legacy observation exists"
    accepted-by: product-owner
separation-policy: [distinct-actor, human-final]
required-sections: [Compared baseline, Results, Regressions, Accepted differences, Decision]
---
# Equivalence report
## Compared baseline
Characterization CHR-001 against conversion CNV-001.
## Results
Observed priced-cart behavior is equivalent.
## Regressions
None.
## Accepted differences
The Product Owner accepts an explicit definition for the unknown empty-cart case.
## Decision
Proceed with accountable acceptance.

