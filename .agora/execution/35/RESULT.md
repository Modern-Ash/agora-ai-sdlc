---
issue: 35
status: implemented
implemented_at: 2026-09-20
implementer: Codex
review: pending-independent
---
# Result: Modernization profile and lifecycle extensions

## Outcome

Added a language- and tool-neutral Modernization profile that keeps the base Core lifecycle intact while gating forward transitions on incremental legacy discovery, conversion, equivalence, cutover, rollback, and stabilization obligations.

## Delivered

- Declarative gate obligations and a transition wrapper over public Core artifact, evidence, work, and transition APIs.
- Ten schema-versioned templates covering inventory through stabilization.
- Explicit known/unknown behavior model that rejects fabricated baselines.
- Unique independently deployable slices traced through plan, conversion, current equivalence report and cutover.
- Semantic equivalence evaluation with Product Owner-authorized accepted differences and fail-closed regressions.
- Evidence-to-current-artifact binding, registered content-digest checks, rollback validation and stabilization enforcement.
- Credential-free sample with a retained failed report, corrected equivalence, explicit unknown behavior and missing rollback path.

## Acceptance evidence

- Plan ids, registered slices and behavior coverage must agree; every slice needs traced conversion and equivalence.
- Unknown behavior can remain unresolved or become an explicitly evidenced and approved difference, but cannot be called equivalent.
- Regression, unknown result, missing comparison, wrong approver, stale digest, wrong evidence target, and old-report evidence block before Core state mutation.
- Completion requires cutover, rollback validation and stabilization evidence bound to the corresponding Core-registered artifacts.

## Limits

- Modernization conformance requires the profile transition wrapper; direct Core transitions enforce only the base Method Pack.
- The profile records and evaluates evidence but does not run discovery, conversion, deployment or rollback tools.
- Behavioral equivalence remains bounded by the characterized cases and accountable accepted differences.
- Independent review remains pending.

## Verification

Focused checks: `61 passed, 1 skipped`; Ruff passed. Full verification: `477 passed, 2 skipped`; all phases passed with ten samples and wheel smoke test.
