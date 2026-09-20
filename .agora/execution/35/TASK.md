---
issue: 35
epic: 5
title: Implement Modernization profile and lifecycle extensions
repository: Modern-Ash/agora-ai-sdlc
base_commit: 6780459
status: review
risk: high
context_size: large
planner: Codex
created_at: 2026-09-20
---
# Task: Implement Modernization profile and lifecycle extensions

## Objective
Compose the base AI-SDLC lifecycle into incremental, traceable modernization slices with explicit legacy behavior, equivalence, cutover, rollback, and stabilization obligations.

## Allowed paths
- `.agora/execution/35/`
- `profiles/modernization/`
- `src/agora_ai_sdlc/modernization.py`
- `src/agora_ai_sdlc/artifacts.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `templates/legacy-inventory.md`
- `templates/dependency-map.md`
- `templates/characterization.md`
- `templates/target-architecture.md`
- `templates/migration-plan.md`
- `templates/migration-slice.md`
- `templates/conversion-record.md`
- `templates/equivalence-report.md`
- `templates/cutover-plan.md`
- `templates/stabilization-report.md`
- `templates/README.md`
- `samples/modernization/`
- `samples/README.md`
- `tests/test_modernization.py`
- `tests/test_modernization_sample.py`
- `tests/test_templates.py`
- `docs/profiles/modernization.md`
- `docs/method/artifacts.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Functional requirements
- Keep the six-state Core lifecycle and enforce profile obligations before supported Core transitions.
- Define discovery, reverse engineering, behavior baseline, target architecture, migration planning, slice, conversion, equivalence, cutover, rollback, and stabilization obligations.
- Represent every migration increment as an independently deployable, uniquely identified slice traced to the migration plan.
- Record known behavior with baseline evidence and unknown behavior with an explicit reason, never an invented baseline.
- Require one conversion and equivalence report per slice; unexplained regression, missing behavior, or unevidenced accepted difference blocks operations.
- Require cutover, rollback validation, and stabilization evidence before completion.
- Remain programming-language and conversion-tool neutral.

## Acceptance criteria
- [x] Each migration slice is independently traceable through plan, conversion, equivalence, and cutover.
- [x] Unknown behavior is recorded without a fabricated baseline.
- [x] Equivalence gate blocks on unexplained regressions and missing/invalid comparisons.
- [x] Rollback and cutover evidence are required before completion.
- [x] Credential-free executable legacy sample covers known and unknown behavior plus failed equivalence and rollback paths.

## Focused verification
- `uv run pytest tests/test_modernization.py tests/test_modernization_sample.py tests/test_templates.py -q`
- `uv run ruff check src/agora_ai_sdlc/modernization.py src/agora_ai_sdlc/artifacts.py tests/test_modernization.py tests/test_modernization_sample.py samples/modernization/run.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- Base AI-SDLC Method Pack and artifact contracts present on `main`.
- Agora Core `list_work_artifacts`, `list_work_evidence`, and `transition_work` APIs.

## Constraints
No new lifecycle states, Core schema changes, language-specific converters, provider SDKs, credentials, or claims that static inventory/equivalence replaces accountable review.
