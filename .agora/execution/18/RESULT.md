---
issue: 18
status: partial
pull_request: pending
---
# Result
`build-verified` and `completion` gates rewritten, 4 templates (incl. rollback-procedure), gate tests, doc.

## Decisions
`operational-readiness` folded into `completion` (3 gates -> 2 transitions), consistent with the choice made for #17. Not re-asked; confirm in review.

## Deviations / limits
- "Open blocking findings prevent completion" is only modelled as a required successful `security-scan` evidence type; Core gates do not read review findings. A later success supersedes an earlier failure.
- No `require-content-addressed-evidence`; revision binding relies on reopen clearing evidence.
- `security-scan` is mandatory in the base completion gate (not profile-optional yet, #20); this adds a step for small teams.
- Added `rollback-procedure` template (issue lists three templates).
