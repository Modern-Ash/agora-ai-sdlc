---
issue: 257
epic: 252
title: Define ExecutionEnvelope v1 with exact Agora-owned next_transition and separate actor/runtime/model identity
base_commit: 3f2a7c1
status: review
planner: Claude
created_at: 2026-09-26
---
# Task #257
Allowed: src/agora_ai_sdlc/execution_envelope.py, runtime_selection.py (public admit_binding), tests/test_execution_envelope.py, docs/architecture.md, .agora/execution/257/**.
Forbidden: adapter command syntax, Core actor schema, new lifecycle, auto-approval, #154 runner UX.
Assumptions to confirm: Core `work_inspection_read_set_sha256` is the Work revision identity; authority = swarm role assignment equals actor reference; operation ids `lifecycle.transition`, `<state>.execute`, `stop.human_authority`; #154 runner integration deferred.
