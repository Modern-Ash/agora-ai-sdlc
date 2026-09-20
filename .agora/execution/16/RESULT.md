---
issue: 16
status: partial
pull_request: pending
---
# Result
`rework-recorded` gate on the 3 rework transitions, lifecycle doc, Core-driven test harness (`tests/support/lifecycle.py`, reusable for #21), lifecycle tests.

## Deviations / assumptions
- Core transitions accept no reason or affected-artifacts fields. Rework is gated on a `rework-record` artifact; reason/affected artifacts are a documented convention, not machine-validated. A single record satisfies the gate for later reworks in the same revision.
- Rework does not increment a revision (Core has no such mechanism); only post-completion `work.reopen` creates a new revision.
- Corrections to PR #50 roles found by running Core: product-owner needed `work.create` (no role could create work) and `work.reopen` (Core authorizes reopen via terminal-transition roles). "Only governance-owner can reopen" is no longer true; tests/doc updated.
- History reconstruction (why/by whom) is only asserted for reopen, not for rework transitions.
