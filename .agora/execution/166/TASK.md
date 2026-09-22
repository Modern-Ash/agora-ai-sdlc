# Task 166 — Observable guided experience

Status: implementing. Authorized by the user's explicit request to implement the preceding design.

## Objective
Keep humans continuously informed without sending the human activity stream back into the agent context. Preserve Core authority and a portable, progressively loaded guided skill.

## Allowed paths
- src/agora_ai_sdlc/observer.py and presentation helpers
- src/agora_ai_sdlc/skill_resources.py
- targeted CLI/start_flow/installer/inception_handoff integrations
- skills/agora-ai-sdlc-guided/**
- corresponding tests, docs/method/observable-experience.md
- .agora/execution/166/**
- temporary .github/workflows/validation-snapshot-166.yml, removed before PR review

## Non-goals
No LLM SDKs or provider-specific runners. No new approval authority, Core schema edits, Work lifecycle bypass, automatic merge, or claim that open #154/#155/#158/#159/#162/#163/#164 are solved. No claims of observed model/provider identity that public Core records do not establish.

## Implementation
1. Read-only bounded observation via public Core APIs; fail closed on ambiguous work selection.
2. Deterministic English/Spanish human views at normal/detailed/diagnostic levels; common machine snapshot independent of language/detail.
3. Explicit human-only output-file channel, bounded watch with heartbeats and cancellation; no narration/model polling.
4. Safe local progress events for Start, based on actual operations, no synthetic percent-complete.
5. Small portable root skill + phase resources; same content through source and installed wheel; installer copies resources.
6. Tests for presentation/context separation, redaction, unknown usage, blocked states, cancellation, validation errors, resource packaging and backwards compatibility.

## Acceptance and evidence
Record commands and real results in TESTS.md. Record limitations and independent-review status in RESULT.md/REVIEW.md; never claim an independent reviewer was run when it was not. Validate complete branch before marking the PR ready.
