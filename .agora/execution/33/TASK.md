---
issue: 33
epic: 5
title: Implement Enterprise profile with signed registry consumption
repository: Modern-Ash/agora-ai-sdlc
base_commit: 0861bfd
status: review
risk: high
context_size: large
planner: Codex
created_at: 2026-09-20
---
# Task: Implement Enterprise profile with signed registry consumption

## Objective
Consume an organization registry as a reviewed, signed, project-local snapshot while keeping organization policy distinct from project customization.

## Allowed paths
- `.agora/execution/33/`
- `profiles/enterprise/`
- `src/agora_ai_sdlc/enterprise.py`
- `src/agora_ai_sdlc/cli.py`
- `src/agora_ai_sdlc/flavor/flavor.yaml`
- `samples/enterprise/`
- `samples/README.md`
- `tests/test_enterprise.py`
- `tests/test_enterprise_sample.py`
- `docs/profiles/enterprise.md`
- `docs/architecture.md`
- `profiles/README.md`
- `README.md`
- `CHANGELOG.md`

## Functional requirements
- Define organization registry source, signature threshold, allowed providers, budget ceilings, and required exported metrics.
- Validate project customization without allowing it to weaken inherited organization policy.
- Install immutable reviewed registry releases into project scope through Agora Core and verify persisted provenance/checksum.
- Preview signed upgrades without writes and apply them transactionally through Agora Core.
- Expose rollback-aware update history and a documented operator rollback procedure.
- Provide a credential-free offline scenario with ephemeral signing material.

## Acceptance criteria
- [x] Untrusted, invalidly signed, or revoked releases fail closed.
- [x] Installed project snapshot records source, version, checksum, verified key ids, and signature threshold.
- [x] Organization policy and project customization are structurally and behaviorally distinct.
- [x] Upgrade is previewable, transactional, conflict-safe, and rollback-aware.
- [x] Multi-project rollout, exceptions, and deployment responsibilities are documented without Control Plane claims.

## Negative cases
- Unknown or disallowed providers, excessive budgets, and missing metrics fail before registry writes.
- Invalid signatures and revoked keys fail installation and update.
- Changed checksum for an installed version and a changed index during apply fail closed.

## Focused verification
- `uv run pytest tests/test_enterprise.py tests/test_enterprise_sample.py -q`
- `uv run ruff check src/agora_ai_sdlc/enterprise.py tests/test_enterprise.py tests/test_enterprise_sample.py samples/enterprise/run.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
- Issue #32 merged at base commit.
- Agora Core `agora-framework>=0.8.2,<0.9` registry trust and update APIs.

## Constraints
No private keys, credentials, provider SDKs, centralized policy service, multi-user management, or duplicated cryptographic/transaction logic.
