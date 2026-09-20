---
issue: 17
status: partial
pull_request: pending
---
# Result
Renamed/reshaped gates (`readiness-approved`, `intent-framed`, `architecture-approved`), 4 templates, gate tests, doc updates.

## Decisions (clarification answered by the user)
Combine: `requirements-approved` folded into `architecture-approved`; 3 gates for 3 transitions.

## Deviations
- Renamed earlier artifact kind `readiness-brief` -> `readiness-assessment`; dropped `domain-model` from required artifacts (replaced by `requirements`).
- Not met: profile composition (#20); "minimal profile cannot remove human ownership" is only checked as the gate requiring product-owner approval.
- Core limits found: approvals not gate-scoped; "same Unit of Work revision" = work revision only.
- No evidence types required in base early gates.
