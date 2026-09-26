---
issue: 253
epic: 252
title: Introduce AgentRuntime / ModelRuntime taxonomy and backward-compatible runtime schema v2
repository: Modern-Ash/agora-ai-sdlc
base_commit: ea6af29
status: review
risk: medium
planner: Claude
created_at: 2026-09-26
---
# Task: AgentRuntime / ModelRuntime taxonomy (runtime-binding/v2)

## Objective
Separate execution host (agent) from model provider/runtime, keeping v1 data loadable.

## Allowed paths
- .agora/execution/253/**
- src/agora_ai_sdlc/runtime_domain.py, runtime_discovery.py, runtime_selection.py, i18n.py
- tests/test_runtime_domain.py
- docs/architecture.md

## Forbidden changes
Capability matching, runtime invocation, Laya semantics, Core actor schema, credentials, auto provider/model choice.

## Acceptance criteria
- AC1 v2 domain types (RuntimeKind, AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding).
- AC2 v1 flat entries normalize deterministically; ambiguous entries raise typed diagnostics.
- AC3 discovery reports agent and model runtimes separately; JSON exposes `kind`; Ollama never counts as an agent host.
- AC4 selection consumes a binding and still accepts RuntimeRef; legacy output fields preserved.
- AC5 credential-free discovery unchanged.
