# Task 166 — Observable guided experience

Status: implemented; independent review pending. Authorized by the user's explicit request to implement the preceding design.

## Objective
Keep humans continuously informed without sending the human activity stream back into agent context. Preserve Core authority and a portable, progressively loaded guided skill.

## Allowed paths
- src/agora_ai_sdlc/observation.py, observation_ui.py, observation_cli.py
- src/agora_ai_sdlc/skill_resources.py
- targeted CLI/start_flow/installer/inception_handoff integrations
- skills/agora-ai-sdlc-guided/**
- corresponding tests, docs/method/observable-experience.md
- .agora/execution/166/**
- temporary .github/workflows/validation-snapshot-166.yml, removed from final tree

## Non-goals
No LLM SDKs or provider-specific runners. No new approval authority, Core schema edits, Work lifecycle bypass, automatic merge, or claim that #154/#155/#158/#159/#162/#163/#164 are solved. No claims of observed model/provider identity that public Core records do not establish.

## Implementation
1. Read-only bounded observation via public Core APIs; explicit Work selection, no bootstrap fallback.
2. Deterministic English/Spanish human views at normal/detailed/diagnostic levels; machine snapshot independent of language/detail.
3. Explicit human-only output-file channel, bounded watch with heartbeats and cancellation; no model narration or polling.
4. Safe local progress events for Start, based on actual operations, no synthetic percent-complete.
5. Small portable root skill plus phase resources; source/installed-wheel equivalence; installer copies all resources.
6. Tests for channel separation, redaction, unknown usage, blocked states, cancellation, validation errors, resource packaging and backwards compatibility.

## Evidence and review
See TESTS.md for commands/results, RESULT.md for limitations, and REVIEW.md for the independent-review boundary. No self-merge or fabricated independent approval.
