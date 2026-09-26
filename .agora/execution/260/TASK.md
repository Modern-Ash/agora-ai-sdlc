---
issue: 260
epic: 252
title: Implement Codex RuntimeAdapter from canonical Agora execution contracts
base_commit: 8e41f3d
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #260
Allowed: src/agora_ai_sdlc/codex_adapter.py, adapters.py, runtime_adapter.py (shared probe helpers), claude_code_adapter.py (use helpers), tests/test_codex_adapter.py, tests/test_claude_code_adapter.py, docs/architecture.md, .agora/execution/260/**.
Forbidden: OpenCode adapter, lifecycle changes, executor_launch wiring, credential access.
Assumptions to confirm: min version 0.156.0 (only 0.156.1 verified); openai-only provider; plain-text output (no --json parsing); sandbox mapping; skills/MCP/subagents/reviewer not projected.
