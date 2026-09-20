---
schema: agora-ai-sdlc/artifact/v1
kind: equivalence-report
version: 1
id: EQV-001
work: feature
revision: 1
traces-to: [CHR-001, CNV-001, MGS-001]
slice-id: checkout-total
comparisons:
  - behavior: priced-cart
    result: regression
    evidence: ["repo://fixtures/priced-cart-failed.json"]
    explanation: "target total differs"
    accepted-by: null
  - behavior: empty-cart-rounding
    result: unknown
    evidence: []
    explanation: "still unobserved"
    accepted-by: null
separation-policy: [distinct-actor, human-final]
required-sections: [Compared baseline, Results, Regressions, Accepted differences, Decision]
---
# Equivalence report
## Compared baseline
Characterization CHR-001 against conversion CNV-001.
## Results
The priced-cart comparison regressed.
## Regressions
Target total differs from the observed baseline.
## Accepted differences
None.
## Decision
Blocked.

