---
issue: 143
title: Local AI runtime discovery and doctor UX
repository: Modern-Ash/agora-ai-sdlc
status: implementing
risk: low
created_at: 2026-09-21
---
# Task: Runtime discovery

## Objective
Detect local Codex, Claude Code, OpenCode and Ollama CLIs without credentials or automatic configuration.

## Allowed paths
- src/agora_ai_sdlc/
- tests/
- docs/
- README.md
- .agora/execution/143/

## Requirements
- credential-free PATH discovery
- bounded version probes
- configured/runtime correlation
- Ollama daemon status
- runtimes and doctor CLI commands
- installer discovery display without auto-enable
- deterministic JSON

## Acceptance criteria
- [x] known CLIs discovered in stable order
- [x] timeout/non-zero handled
- [x] configured state correlated
- [x] Ollama service state separated from CLI state
- [x] installer remains explicit
- [x] CLI/JSON surfaces added
- [ ] full CI green
