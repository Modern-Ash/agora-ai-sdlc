---
issue: 261
epic: 252
title: Implement OpenCode RuntimeAdapter and compose Ollama as a ModelRuntime
base_commit: 9d20b6e
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #261
Allowed: src/agora_ai_sdlc/opencode_adapter.py, adapters.py, runtime_discovery.py (model catalog), runtime_selection.py (model presence, binding candidate id), tests/test_opencode_adapter.py, tests/test_claude_code_adapter.py, tests/test_codex_adapter.py, docs/architecture.md, .agora/execution/261/**.
Forbidden: opencode_runner changes, model pull/download, lifecycle changes, credential access.
Assumptions to confirm: min version 1.0.0 (only 1.18.32 verified); provider config stays inline per invocation (nothing persisted); OpenCode requires an explicit model; candidate id for bindings is `agent+provider/model`; `default_registry` now takes a root.
