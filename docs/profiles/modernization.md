# Modernization profile

Modernization composes the unchanged six-state AI-SDLC lifecycle into incremental legacy-system migration. Agora Core remains lifecycle authority and stores artifacts, evidence, approvals, criteria and transitions. `agora_ai_sdlc.modernization.transition` evaluates the additional profile obligations immediately before delegating a forward transition to Core; rework transitions remain the base Method Pack transitions.

Use the profile wrapper for Modernization work. Calling Core `transition_work` directly evaluates only the base Method Pack and does not claim conformance to this profile.

## Lifecycle mapping

| Core gate | Modernization obligation |
| --- | --- |
| `readiness-approved` | Legacy inventory, dependency map and behavior characterization |
| `intent-framed` | Base product intent and criterion elaboration |
| `architecture-approved` | Target architecture, migration plan and at least one independently deployable migration slice |
| `build-verified` | One traced conversion and equivalence report per slice plus successful `behavioral-equivalence` evidence bound to a report |
| `completion` | Cutover plan, rollback procedure, stabilization report and successful `cutover`, `rollback-validation` and `stabilization` evidence bound to those artifacts |

These are profile obligations, not new lifecycle states. A `migration-slice` is a bounded increment inside one Unit of Work. Each slice has a unique `slice-id`, lists the characterized behavior it covers, traces to the migration plan, and must be independently deployable. The plan's slice ids and the registered slice set must match; their combined behavior ids must match the characterization scope.

## Behavior truth

Characterization records each behavior as either:

- `known`: a non-empty observed baseline and at least one evidence reference, with no speculative reason.
- `unknown`: `baseline: null`, no baseline evidence, and a non-empty reason explaining the observation gap.

Unknown behavior is never inferred from code shape, model output, documentation, or a target implementation. It cannot be marked `equivalent`. Before operations it must remain blocked or become an `accepted-difference` with evidence, explanation and Product Owner acceptance.

## Slice traceability

The profile validates this chain using immutable artifact ids and Core-recorded content digests:

```text
legacy inventory -> dependency map / characterization -> target architecture
  -> migration plan -> migration slice -> conversion record -> equivalence report
  -> cutover plan -> stabilization report
```

Every behavior assigned to a slice needs exactly one current comparison in that slice's equivalence report. `equivalent` requires evidence. `accepted-difference` requires evidence, explanation and `accepted-by: product-owner`. `regression`, `unknown`, missing comparisons, comparisons outside the slice, stale digests, missing conversion, or bad trace edges fail closed.

Correcting a failed comparison creates a new equivalence-report artifact with a new id. Core retains the failed report and evidence; the latest registered report for that slice drives the next assessment. Do not overwrite a registered file because its content digest will become stale.

## Cutover and rollback

The cutover plan covers every slice and traces to each current equivalence report. The stabilization report covers the same slice set and traces to cutover. Successful evidence must reference the corresponding registered artifact, not merely reuse an evidence type name.

Completion requires rollback validation in addition to the base `rollback-procedure`. A failed or absent validation blocks completion. Rework uses `operations -> construction`, retains prior records, and produces a new conversion/equivalence revision before another cutover attempt.

## Responsibilities and limits

The profile is programming-language, runtime, converter and provider neutral. Teams choose discovery and conversion tools, but must record exact inputs, procedures, outputs, exceptions and reproducibility. Inventory and generated analysis are evidence inputs, not ground truth; accountable humans resolve scope, accepted differences, cutover and retirement decisions.

This profile does not execute converters, infer unknown behavior, prove semantic equivalence for arbitrary systems, deploy production traffic, or replace customer backup and disaster-recovery controls.

The credential-free [Modernization sample](../../samples/modernization/README.md) demonstrates known and unknown behavior, a failed equivalence gate, an accepted difference, missing rollback evidence, re-evaluation and successful Core completion.

