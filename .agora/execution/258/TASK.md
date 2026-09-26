---
issue: 258
epic: 252
title: Add provider-neutral RuntimeAdapter SPI and native projection infrastructure
base_commit: c8d1e90
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #258
Allowed: src/agora_ai_sdlc/runtime_adapter.py, tests/test_runtime_adapter.py, tests/support/adapter_conformance.py, docs/architecture.md, .agora/execution/258/**.
Forbidden: concrete Claude/Codex/OpenCode adapters (#259-261), installer UX, Laya, MCP client, lifecycle changes.
Assumptions to confirm: managed surfaces limited to marked text blocks and top-level JSON keys; backups under .agora/ai-sdlc/backups/<adapter>/; registry keyed by canonical agent id; workspace scope only (global scope not implemented).
