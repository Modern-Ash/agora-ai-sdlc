---
issue: 256
epic: 252
title: Add deterministic capability admission between runtime selection and executor launch
base_commit: 1a4a5d2
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #256
Allowed: src/agora_ai_sdlc/runtime_selection.py, tests/test_capability_admission.py, docs/architecture.md, .agora/execution/256/**.
Forbidden: adapters, auto-install, credentials, Laya, retry on execution failure.
AC per issue. Assumptions to confirm: opt-in `capability-mismatch` fallback signal; local tier requires an explicit model binding; agent without model_selection cannot take a model binding.
