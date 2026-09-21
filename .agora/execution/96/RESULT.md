---
issue: 96
status: partial
commit: 6eebc988063208acc919d457ad9a696d16015bc9
pull_request: 110
updated_at: 2026-09-21
---
# Result

## Status
Implementation and automated verification are complete. Independent review remains required before Definition of Done.

## Concise summary
Added machine-readable AWS-original fidelity rules that inspect Agora AI-SDLC repository assets and derive generic conformance facts. The rules distinguish base public-method fidelity from Agora-specific additive governance and are exposed through `agora-ai-sdlc conformance aws-original --derive`.

## Files modified
- `profiles/compatibility/aws-original/profile.yaml`
- `contracts/conformance/aws-original-rules-v1.schema.json`
- `contracts/conformance/aws-original-rules-v1.yaml`
- `src/agora_ai_sdlc/conformance/aws_original.py`
- `src/agora_ai_sdlc/conformance/__init__.py`
- `src/agora_ai_sdlc/cli.py`
- `tests/conformance/test_aws_original_rules.py`
- `tests/fixtures/conformance/aws-original/current.yaml`
- `tests/test_cli.py`
- `docs/reference/conformance.md`
- `docs/reference/aws-ai-dlc-mapping.md`
- `.agora/execution/96/*`

## Decisions made
- aws-original profile version is 1.1.0 and explicitly includes `three-phase-lifecycle`, `minimal-roles` and `operations-governed-remediation`.
- A closed check vocabulary evaluates files, content and Method Pack front matter deterministically.
- Base-method rules feed the generic #95 evaluator.
- Agora additions such as fail-closed gates, independent review, provider neutrality and model provenance are reported separately and do not affect AWS-original base fidelity.
- Optional capabilities without evidence remain NOT_APPLICABLE.
- Rules cannot escape the supplied repository root and perform no network access.
- #96 remains stacked on #95 / PR #109 and must merge after it.

## Current evidence-backed fidelity result
Against the current repository:
- PASS: 11 capabilities
- PARTIAL: 10 capabilities
- FAIL: `recursive-planning`
- NOT_APPLICABLE: optional `prfaq`

The overall result is therefore FAIL today. This is intentional and truthful: the conformance provider exposes implementation gaps rather than converting roadmap documentation into passing evidence.

## Automated verification
GitHub Actions run #97 passed:
- Python 3.11: full `verify_all.py`
- Python 3.12: full `verify_all.py`
- Python 3.13: full `verify_all.py` (617 passed, 16 skipped)
- Agora Core 0.9.1 compatibility: 631 passed, 2 skipped

Evidence: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35616365363

## Deviations
No requested behavior was omitted. The public-method rule provider intentionally does not treat Agora additive governance as evidence that upgrades base fidelity.

## Remaining risks
- Independent review by a different session/runtime is pending.
- The rules assess checked-in implementation evidence; they do not constitute AWS certification, endorsement or affiliation.
- The current Method Pack still has known fidelity gaps, most notably recursive Level-N planning and several partial artifact/lifecycle capabilities.

## Pending work
Independent review, merge #95 first, then retarget/merge #96.

## Commit and pull request
Draft PR #110: https://github.com/Modern-Ash/agora-ai-sdlc/pull/110
