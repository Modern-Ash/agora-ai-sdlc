---
issue: 95
status: partial
commit:
pull_request:
updated_at: 2026-09-21
---
# Result

## Status
Implementation complete; automated verification and independent review pending.

## Concise summary
Added a generic, offline compatibility conformance engine, versioned facts/result contracts, CLI command, strict mode, deterministic evaluation semantics and tests. Methodology-specific rule derivation remains intentionally outside this issue.

## Files modified
- src/agora_ai_sdlc/conformance/compatibility.py
- src/agora_ai_sdlc/conformance/__init__.py
- src/agora_ai_sdlc/cli.py
- contracts/conformance/conformance-facts-v1.schema.json
- contracts/conformance/conformance-result-v1.schema.json
- tests/conformance/test_compatibility_engine.py
- tests/test_cli.py
- docs/reference/conformance.md
- .agora/execution/95/*

## Decisions made
- Facts are a local versioned contract rather than a vendor API.
- Required capabilities fail closed when facts are missing or marked NOT_APPLICABLE.
- Optional missing facts are NOT_APPLICABLE.
- Unsupported profile capabilities render NOT_APPLICABLE.
- Unknown fact capabilities are rejected to prevent silent typos.
- Non-strict CLI reports valid failing conformance with exit 0; --strict returns 1 when any FAIL exists; invalid inputs return 2.
- This engine does not infer methodology-specific evidence. Issue #96 adds fidelity rules/providers.

## Criteria satisfied
Implementation addresses all functional criteria in issue #95; automated verification is pending.

## Tests run
Pending pull-request CI.

## Results
Pending.

## Deviations
None known.

## Remaining risks
- CI may expose formatting or integration regressions.
- Independent review remains required.
- Without a local facts file or later rule provider, required capabilities deliberately fail closed.

## Pending work
Run CI, fix failures, record final evidence, independent review.

## Commit and pull request
Branch: feat/95-conformance-engine
Pull request: pending
