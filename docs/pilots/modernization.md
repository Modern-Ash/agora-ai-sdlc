# Incremental modernization pilot

## Scope and evidence boundary

The pilot uses the language- and tool-neutral checkout-total slice from the [Modernization profile](../profiles/modernization.md) sample. It runs offline against a real Agora Core workspace with the unchanged six-state AI-SDLC lifecycle, so lifecycle gates, artifacts, evidence and validation are exercised. It does not run a real legacy system, a real converted system or a live model, so conversion quality and behavioral equivalence of real code are not measured.

```console
uv run agora-ai-sdlc run-sample modernization
```

## Baseline

| Fact | Value |
| --- | --- |
| Slice | `checkout-total` (one incremental slice) |
| Behaviors characterized as known | `priced-cart` |
| Behaviors left explicitly unknown | `empty-cart-rounding` |
| Starting lifecycle state | `readiness` |

Unknown behavior is never treated as equivalent: it stays visible until a human accepts a documented difference.

## Offline flow

1. Register the legacy inventory, dependency map and characterization; move through `intent` and `inception` with the target architecture, migration plan and migration slice.
2. Construction registers the conversion record and a first equivalence report in which `priced-cart` regressed. The behavioral-equivalence evidence is a failure, so construction to operations is blocked by `modernization.gate.blocked`.
3. A passing equivalence report is registered with successful evidence, and the transition to operations succeeds.
4. Operations registers the cutover plan and stabilization report with their evidence. Completion is blocked a second time because rollback validation is missing.
5. Rollback validation evidence is recorded, the accountable role completes the work, and Core validation passes.

## Outcome

| Measured offline fact | Result |
| --- | --- |
| Final lifecycle state | `completed` |
| Gate blocks before completion | 2 (failed equivalence, missing rollback validation) |
| Accepted difference | `empty-cart-rounding` |
| Rollback validated | yes |
| `agora validate` | ok |

## Evidence

The JSON printed by the command is the machine-checkable record: `slice_ids`, `known_behaviors`, `unknown_behaviors`, `blocked_paths`, `accepted_difference`, `rollback_validated`, `final_state` and `validate`. The fixtures under `samples/modernization/fixtures/` are the registered artifacts. `tests/test_modernization_pilot.py` fails if this report and the command output disagree.

## Limitations

- The outcome comes from deterministic fixtures. It shows that the profile blocks and unblocks as designed, not that any real migration would pass.
- Delivery speed, defect rates, semantic equivalence of real code, production stability and cost are not measured and are not claimed. They remain explicit expectations for a live pilot.
- One slice does not show cross-slice ordering, data migration or parallel-run behavior.

## Optional live pilot

Live execution is operator-controlled and never part of default CI.

1. Work in a disposable clone of one real legacy module and record the installed Agora Core version and the Method Pack digest.
2. Characterize observable behavior before converting anything; record unobserved behavior as unknown.
3. Convert one slice, run the legacy and target implementations against the same inputs, and register the comparison as equivalence evidence. Do not weaken a regression into an accepted difference without a named human owner and reason.
4. Register cutover, stabilization and rollback-validation evidence from real runs, then complete through the normal gates and run `agora validate`.
5. Record every observation as measured and every extrapolation as an expectation. Do not place credentials, private data or raw production output in the repository or Agora artifacts.

A live pass applies only to the recorded slice, revision and date and is not a compliance or migration-success guarantee.
