---
issue: 141
epic:
title: Guided AI-SDLC UX
repository: Modern-Ash/agora-ai-sdlc
base_commit: baa830ff58535975432d546ae8286fe874fb5898
status: implementing
risk: medium
context_size: bounded
budget:
  max_input_tokens: 12000
  max_output_tokens: 4000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Guided AI-SDLC UX

## Objective
Implement the first guided UX slice from issue #141 without duplicating Agora Core lifecycle semantics.

## Business outcome
Normal users see human decisions rather than raw Core blocker arrays, while selected agents receive one portable skill that wraps Core commands.

## Current state
Installer hands users directly to `agora continue`, exposing Core-level gate details.

## Required inputs
- issue #141
- AGENTS.md
- existing installer and CLI
- packaged readiness-assessment template

## Allowed paths
- src/agora_ai_sdlc/
- skills/
- tests/
- docs/
- README.md
- pyproject.toml
- .agora/execution/141/

## Forbidden changes
- Agora Core repository
- Method Pack gate semantics
- automatic human approval
- provider-specific SDK dependencies

## Functional requirements
- guided `continue` projection
- normal/expert disclosure
- portable guided agent skill
- installer copies skill into target project
- Core remains lifecycle authority

## Acceptance criteria
- [x] default output hides raw blockers
- [x] expert mode preserves raw blockers
- [x] installed project receives portable skill
- [x] skill forbids silent human approval/role transfer
- [x] no Core lifecycle duplication

## Negative cases
- no next action
- unknown/unstructured blocker
- missing packaged skill

## Focused verification
Pytest coverage added for guided projection, CLI modes and installer skill copy.

## Full verification
GitHub Actions required; local clone unavailable in this execution environment.

## Dependencies
Agora Core >=0.8.2,<0.10.

## Clarifications
None required for the vertical slice.

## Completion evidence
Branch feat/141-guided-ai-sdlc-ux and PR.
