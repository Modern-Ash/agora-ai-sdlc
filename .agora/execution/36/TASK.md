---
issue: 36
epic: 6
title: Define cross-repository AI-SDLC projection contract
repository: Modern-Ash/agora-ai-sdlc
base_commit: 6594de7
status: review
risk: high
context_size: large
planner: Codex
created_at: 2026-09-20
---
# Task: Define cross-repository AI-SDLC projection contract

## Objective
Publish a versioned, provider-neutral read contract that Core can produce and Studio can render without parsing flavor Markdown or receiving browser-supplied filesystem paths.

## Allowed paths
- `.agora/execution/36/`
- `.agora/context/integration-contracts.md`
- `contracts/studio/`
- `docs/integrations/studio-projection.md`
- `docs/architecture.md`
- `README.md`
- `CHANGELOG.md`
- `pyproject.toml`
- `scripts/verify_all.py`
- `tests/test_studio_projection_contract.py`
- upstream issues in `Modern-Ash/agora` and `Modern-Ash/agora-studio`

## Functional requirements
- Specify flavor/profile metadata, generic lifecycle state, clarifications, model/runtime provenance, separation status and metrics.
- Make every optional projection explicitly `available` or `unavailable` with a stable reason.
- Keep presentation hints separate and non-authoritative.
- Use a server-issued selection id and logical project/work identifiers; accept no browser filesystem path.
- Permit unknown future state ids and additive fields within v1.
- Inventory current Core 0.8.2 and Studio 0.5.0 support and open upstream gap issues.

## Acceptance criteria
- [x] Contract contains no browser-supplied filesystem path.
- [x] Unknown future lifecycle states validate and can render generically.
- [x] Missing projections use explicit unavailable envelopes.
- [x] Studio needs no flavor Markdown parser.
- [x] Compatibility table and owning-repository gaps are published.

## Verification
- `.venv/bin/pytest tests/test_studio_projection_contract.py tests/test_flavor_manifest.py -q`
- `.venv/bin/ruff check tests/test_studio_projection_contract.py`
- `uv run python scripts/verify_all.py`

## Dependencies and observations
- Agora Core 0.8.2 public application services already expose lifecycle v3, traceability/clarifications v2, sessions v1 and project metrics/counts.
- Agora Core issue #54 already tracks complete provider-neutral runtime provenance.
- Agora Studio 0.5.0 consumes exact Core 0.8 schemas, but its current project-open flow exposes a local path to the browser and it has no AI-SDLC aggregate.
- Upstream implementation gaps: Modern-Ash/agora#55 and Modern-Ash/agora-studio#10.

## Constraints
No Core/Studio implementation, browser UI, filesystem parser, lifecycle authority, credentials, private keys, provider SDK, or hard-coded AI-SDLC state list in this repository change.
