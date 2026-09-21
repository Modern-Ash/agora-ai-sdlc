---
issue: 96
status: partial
commit:
pull_request:
updated_at: 2026-09-21
---
# Result

## Status
Implementation complete; automated verification and independent review pending.

## Concise summary
Added versioned AWS-original fidelity rules that derive generic conformance facts from repository evidence, separate AWS base-method fidelity from Agora additive governance, and expose an explicit --derive CLI mode.

## Files modified
- profiles/compatibility/aws-original/profile.yaml
- contracts/conformance/aws-original-rules-v1.schema.json
- contracts/conformance/aws-original-rules-v1.yaml
- src/agora_ai_sdlc/conformance/aws_original.py
- src/agora_ai_sdlc/conformance/__init__.py
- src/agora_ai_sdlc/cli.py
- tests/conformance/test_aws_original_rules.py
- tests/fixtures/conformance/aws-original/current.yaml
- tests/test_cli.py
- docs/reference/conformance.md
- docs/reference/aws-ai-dlc-mapping.md
- .agora/execution/96/*

## Decisions made
- The aws-original compatibility contract is bumped to 1.1.0 to add explicit three-phase-lifecycle, minimal-roles and operations-governed-remediation capabilities.
- Rules are data-driven and use a closed offline check vocabulary.
- Base-method rules feed the generic #95 engine.
- Agora additive governance is evaluated separately and cannot alter AWS base-method fidelity.
- Required capabilities produce PASS/PARTIAL/FAIL; absent optional capabilities remain NOT_APPLICABLE.
- --derive is explicit and mutually exclusive with --facts.
- #96 is stacked on #95 / PR #109 and must merge after it.

## Criteria satisfied
Implementation covers the issue #96 rule set, explicit evidence mapping, additive-governance separation and golden current-state fixture. Automated verification is pending.

## Tests run
Pending pull-request CI.

## Results
Pending.

## Deviations
None known.

## Remaining risks
- CI may expose formatting or golden-status mismatches against actual repository contents.
- Independent review remains required.
- This is a public-method fidelity implementation, not AWS certification or endorsement.

## Pending work
Run CI, correct failures, record final evidence, independent review.

## Commit and pull request
Branch: feat/96-aws-fidelity-rules
Pull request: pending
