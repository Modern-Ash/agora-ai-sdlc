---
issue: 34
epic: 5
title: Implement Regulated profile and segregation controls
repository: Modern-Ash/agora-ai-sdlc
base_commit: 1997bf2
status: review
risk: high
context_size: large
planner: Codex
created_at: 2026-09-20
---
# Task: Implement Regulated profile and segregation controls

## Objective
Compose the regulated depth, Core signed lifecycle actions, independent review, and complete observed runtime provenance into a fail-closed adoption profile.

## Allowed paths
- `.agora/execution/34/`
- `profiles/regulated/`
- `src/agora_ai_sdlc/regulated.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `tests/test_regulated.py`
- `docs/profiles/regulated.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Functional requirements
- Require Core Ed25519 authentication for actors that perform critical lifecycle actions.
- Reject prohibited role combinations and non-human accountable approval roles before assignment or use.
- Require complete observed model/runtime provenance before AI execution.
- Validate and persist explicit, authorized, time-bound exception and evidence-retention records without secrets.
- Keep Core authoritative for lifecycle state, actor identity, signatures, and stale preconditions.
- Distinguish provided controls from customer compliance responsibilities and make no certification claim.

## Acceptance criteria
- [x] Unsigned critical actions are rejected by Core.
- [x] Prohibited role combinations are rejected before assignment and by swarm preflight.
- [x] Exceptions are explicit, authorized, time-bound, immutable and auditable.
- [x] Evidence retention metadata is required and immutable.
- [x] Incomplete or merely declared AI provenance blocks execution.
- [x] Documentation makes no regulatory certification claim.

## Verification
- `uv run pytest tests/test_regulated.py tests/test_independent_review.py tests/test_provenance.py -q`
- `uv run ruff check src/agora_ai_sdlc/regulated.py tests/test_regulated.py`
- `uv run python scripts/verify_all.py`

## Constraints
Production deployments use organization-managed actor keys. Tests use ephemeral keys only. No private keys, provider credentials, lifecycle replacements, provider SDKs, or claims of legal compliance.
