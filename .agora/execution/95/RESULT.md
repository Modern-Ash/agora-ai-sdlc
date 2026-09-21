---
issue: 95
status: partial
commit: b66436521628bf78dc479e9e791f157e04d1f332
pull_request: 109
updated_at: 2026-09-21
---
# Result

## Status
Implementation and automated verification are complete. Independent review is still required before Definition of Done.

## Concise summary
Added a generic, offline compatibility conformance engine with versioned local facts and result contracts, deterministic capability evaluation, human/JSON CLI output and strict mode. The engine is vendor-neutral and intentionally separates generic evaluation from methodology-specific evidence derivation.

## Files modified
- `src/agora_ai_sdlc/conformance/compatibility.py`
- `src/agora_ai_sdlc/conformance/__init__.py`
- `src/agora_ai_sdlc/cli.py`
- `contracts/conformance/conformance-facts-v1.schema.json`
- `contracts/conformance/conformance-result-v1.schema.json`
- `tests/conformance/test_compatibility_engine.py`
- `tests/test_cli.py`
- `docs/reference/conformance.md`
- `.agora/execution/95/*`

## Decisions made
- Capability facts are local/versioned inputs rather than vendor API results.
- Required capabilities fail closed when missing and when explicitly marked NOT_APPLICABLE.
- Optional missing capabilities become NOT_APPLICABLE.
- Unsupported profile capabilities render NOT_APPLICABLE.
- Unknown fact capabilities are rejected to prevent silent misspellings or unrelated evidence.
- Overall status precedence is FAIL, PARTIAL, PASS, then NOT_APPLICABLE.
- Valid failing reports return 0 by default; `--strict` returns 1 when any FAIL exists; invalid input returns 2.
- The engine does not hard-code AWS/LG scoring rules. Issue #96 supplies methodology-specific fidelity facts/rules.

## Criteria satisfied
All issue #95 functional criteria are implemented and covered:
- deterministic project/repository fact evaluation;
- four result statuses per capability;
- evidence/reason/source contract version/remediation in output;
- human and JSON CLI;
- strict/non-strict exit behavior;
- fail-closed required capabilities;
- stable invalid-input errors;
- offline/no-network operation;
- checked-in facts and result schemas;
- existing CLI and full repository behavior preserved.

## Automated verification
GitHub Actions run #91 passed:
- Python 3.11: full `verify_all.py`
- Python 3.12: full `verify_all.py`
- Python 3.13: full `verify_all.py` (605 passed, 16 skipped)
- Agora Core 0.9.1 compatibility: 619 passed, 2 skipped

Evidence: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35614225775

## Deviations
No requested product behavior was omitted. Focused commands were not separately executed because the full CI path exercised the same modules plus the complete repository verification.

## Remaining risks
- Independent review by a different session/runtime remains pending; the implementer does not author `REVIEW.md`.
- The engine consumes explicit facts. Automatic fidelity evidence derivation is intentionally deferred to #96.
- Without facts or a later rule provider, required capabilities correctly fail closed.

## Pending work
Independent review and human merge decision.

## Commit and pull request
Draft PR #109: https://github.com/Modern-Ash/agora-ai-sdlc/pull/109
