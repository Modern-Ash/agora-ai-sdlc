---
issue: 262
epic: 252
title: Bind review and verification to immutable candidate identity using existing Core evidence primitives
base_commit: 4c7f0aa
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #262
Allowed: src/agora_ai_sdlc/execution_candidate.py, execution_envelope.py (optional `candidate` field), tests/test_execution_candidate.py, docs/architecture.md, .agora/execution/262/**.
Forbidden: RDD/receipt store, new Core gate, auto-approval, auto-commit.
Assumptions to confirm: candidate kinds; worktree snapshot bounds (500 files, 1 MB); Core computes artifact content digests from `artifact_refs`; `session_id` only when installed Core supports it; wiring into the review flow/adapters deferred.
