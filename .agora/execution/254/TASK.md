---
issue: 254
epic: 252
title: Add canonical AgentCapabilityManifest v1 and fail-closed runtime capability registry
base_commit: 85f81a5
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #254
Allowed: src/agora_ai_sdlc/agent_capabilities.py, cli.py (runtimes --capabilities), tests/test_agent_capabilities.py, docs/architecture.md, .agora/execution/254/**.
Forbidden: capability admission/matching (#256), adapters, lifecycle state in manifests.
AC: versioned manifest; explicit ids; registry for claude/codex/opencode; fail closed on unknown; CLI/JSON inspectable; deterministic digest; extension docs.
Assumption to confirm: capability claims are conservative (codex subagents=false, opencode skills/structured_output=false, isolated_reviewer=false for all).
