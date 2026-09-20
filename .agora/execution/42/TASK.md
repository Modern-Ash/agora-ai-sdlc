---
issue: 42
epic: 8
title: Produce vendor-neutral reference architecture and shared-responsibility model
repository: Modern-Ash/agora-ai-sdlc
base_commit: fc6a2b1
status: review
risk: medium
context_size: medium
planner: Codex
created_at: 2026-09-20
---
# Task: Vendor-neutral reference architecture and shared-responsibility model

## Objective

Publish a procurement-ready architecture and responsibility model that accurately maps the shipped AI-SDLC distribution to local, CI, and self-managed enterprise deployments without making a provider mandatory or overstating Agora enforcement.

## Allowed paths

- `.agora/execution/42/`
- `docs/commercial/`
- `tests/test_commercial_architecture.py`
- `tests/test_commercial_packages.py`

## Forbidden changes

- Product runtime behavior, manifests, profiles, policies, Method Packs, or samples
- Provider SDKs, credentials, deployment automation, hosted services, or cloud endorsement
- Claims of compliance, certification, production guarantees, or a currently available Control Plane

## Functional requirements

- Describe developer-workstation, CI-automation, and self-managed enterprise patterns.
- Show Core, flavor, Studio, external runtime, external tool, Git, and project-state boundaries accurately.
- Identify replaceable runtime, provider, integration, registry transport, observability, and presentation points.
- Assign identity, credentials, isolation, data residency, model terms, backups, and incident response.
- Separate Agora enforcement and validation from evidence supplied by a deployment and controls operated by a customer or provider.
- Document failure and recovery behavior, including unavailable optional components and partial enterprise rollout.
- Provide AWS, Azure, GCP, and on-premises examples only as optional mappings after the neutral architecture.

## Acceptance criteria

- [x] Core, flavor, Studio, and external-tool boundaries match repository contracts.
- [x] The primary diagram is technology-neutral and no cloud is mandatory.
- [x] Security controls distinguish Agora enforcement from deployment responsibility.
- [x] Failure and recovery paths are documented.

## Negative cases

- Cloud-vendor names in the primary diagram fail documentation tests.
- Missing deployment patterns, required responsibility topics, or recovery cases fail documentation tests.
- Claims that Studio writes project state, Agora stores credentials, or a hosted Control Plane exists fail documentation tests.

## Focused verification

- `uv run pytest tests/test_commercial_architecture.py tests/test_commercial_packages.py -q`
- `uv run ruff check tests/test_commercial_architecture.py tests/test_commercial_packages.py`

## Full verification

- `uv run python scripts/verify_all.py`

## Dependencies

- #32 Enterprise profile is implemented.
- #29 observability and operational-evidence profile is implemented.
- Repository boundaries, security policies, executable samples, and service packages are present on `main`.

## Clarifications

Cloud mappings name illustrative customer-selected services but do not add adapters, deployment support, certification, or endorsement.

## Completion evidence

Documentation and verification in progress; independent review pending.
