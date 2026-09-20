---
issue: 15
status: partial
pull_request: pending
---
# Result
9 roles, docs/method/roles.md, role conformance tests.

## Deviations / assumptions
- Core role schema has no delegation or combination fields; delegation rules and combinations are documented in role bodies and roles.md, and checked structurally only.
- Not done: live human/AI/delegated execution and accountable-holder retention through Core (needs #21).
- Only the 5 original roles stay in `required-roles` so small teams remain usable; the 4 new roles are optional.
- Prohibited regulated combinations are documented, not enforced (#22, #34).
- Action names come from Core's vocabulary; `work.delegate` and `gate.waive` are assumed to be valid role actions (installs and validates in 0.8.2).
