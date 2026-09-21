---
issue: 129
epic: 92
title: Add end-to-end adaptive planning reference sample
repository: Modern-Ash/agora-ai-sdlc
status: implementing
risk: medium
context_size: medium
planner: ChatGPT
created_at: 2026-09-21
---
# Task

## Objective
Add one executable credential-free reference sample that composes Method Pack 0.2.0, recursive approved plans, parallel Bolts, context assembly and the real Core lifecycle through completion.

## Allowed paths
- .agora/execution/129/**
- samples/adaptive-delivery/**
- samples/README.md
- tests/test_adaptive_delivery_sample.py

## Forbidden changes
- Agora Core
- Method Pack semantics
- plan/Bolt/context contracts
- provider/network integrations

## Acceptance criteria
- Method Pack 0.2.0 is used.
- Level 1 and Level 2 plans parse, validate and are executable.
- Two Bolts are simultaneously ready for parallel execution.
- Final Bolt plan has complete construction evidence.
- Context bundle includes the Unit/Plan/Bolt chain and excludes unrelated artifacts.
- Real lifecycle reaches completed and `agora validate` passes.
- Full CI passes.
