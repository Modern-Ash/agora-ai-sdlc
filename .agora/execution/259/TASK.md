---
issue: 259
epic: 252
title: Implement Claude Code RuntimeAdapter from canonical Agora execution contracts
base_commit: 5b0e2aa
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #259
Allowed: src/agora_ai_sdlc/claude_code_adapter.py, adapters.py, runtime_adapter.py (stale check), tests/test_claude_code_adapter.py, docs/architecture.md, .agora/execution/259/**.
Forbidden: Codex/OpenCode adapters, lifecycle changes, wiring into #154 handoff/executor_launch, credential access.
Assumptions to confirm: min supported version 2.1.0 (only 2.1.281 verified); skills/MCP/subagents/reviewer intentionally not projected; permission mode acceptEdits and the Bash allow-list mirror executor_adapters.yaml; envelope sent on stdin.
