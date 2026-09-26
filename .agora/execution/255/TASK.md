---
issue: 255
epic: 252
title: Project deterministic + Laya advisory signals into provider-neutral ExecutionRequirements
base_commit: 6d5d1f5
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #255
Allowed: src/agora_ai_sdlc/execution_requirements.py, tests/test_execution_requirements.py, docs/architecture.md, .agora/execution/255/**.
Forbidden: runtime selection, admission (#256), adapters, Laya changes, lifecycle authority.
AC: byte-stable JSON; safe without Laya; low-confidence fails open; provider-neutral tiers; human non-executable; checkpoint is provenance; no provider branching.
Assumption to confirm: activity classes and the action->capability table; risk/tier/security only ever raised by advisory.
