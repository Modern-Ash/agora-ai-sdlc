---
issue: 106
epic: 93
title: Add change/configuration management and domain-knowledge source contracts
repository: Modern-Ash/agora-ai-sdlc
base_commit: ee3a06867ebedf70fc939d4b95ca2a53034f2e2c
status: implementing
risk: medium
context_size: medium
budget:
  max_input_tokens: 38000
  max_output_tokens: 16000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Add change/configuration management and domain-knowledge source contracts

## Objective
Add provider-neutral, versioned contracts for governed change/configuration chains and reusable domain-knowledge source descriptors.

## Business outcome
Enterprise delivery can prove why a change exists, what approved plan governs it, what configuration changed, which release evidence proves delivery, how rollback is linked, and which reusable knowledge sources were authorized without embedding credentials/provider endpoints.

## Current state
Cross-repository impact analysis and enterprise review gates are on main. The repository has generic traceable artifacts, exact-revision approval patterns, data-classification policy and offline samples, but no dedicated change/configuration chain or neutral domain-knowledge descriptor.

## Allowed paths
- .agora/execution/106/**
- src/agora_ai_sdlc/artifacts.py
- src/agora_ai_sdlc/change_management.py
- src/agora_ai_sdlc/domain_knowledge.py
- templates/change-request.md
- templates/change-plan.md
- templates/configuration-delta.md
- templates/README.md
- contracts/enterprise/change-management-v1.schema.json
- contracts/enterprise/domain-knowledge-source-v1.schema.json
- tests/test_change_management.py
- tests/test_domain_knowledge.py
- tests/test_templates.py
- tests/fixtures/change-management/**
- tests/fixtures/domain-knowledge/**
- samples/change-management/**
- samples/domain-knowledge/**
- samples/README.md
- tests/security/test_secret_leaks.py
- docs/method/change-management.md
- docs/method/domain-knowledge.md
- docs/method/artifacts.md

## Forbidden changes
- Agora Core
- Method Pack lifecycle/transitions/roles
- provider SDK/API calls
- embedded credentials, tokens, Authorization headers or raw provider endpoints in knowledge descriptors
- hidden remote discovery
- automatic external-system mutation

## Functional requirements
### Change/configuration
- Register change-request, change-plan and configuration-delta artifact kinds.
- Change request traces to Unit or impact-analysis.
- Change plan traces to change-request and may also trace to Level-N Plan.
- Configuration delta traces to change-plan.
- Change plan approval is exact-revision and accountable-human bound.
- Configuration delta records changed keys/resources without secret values.
- Configuration delta requires release evidence references and rollback linkage.
- Release evidence and rollback references use credential-free opaque/local refs.
- Deterministic chain validator proves request -> approved plan -> delta -> release/rollback linkage.

### Domain knowledge
- Versioned descriptor contract supporting repository-docs, wiki, files, api and vector-store source kinds.
- Descriptor contains references/metadata only; no fetched content.
- Provider-neutral id, classification, owner, revision, scope and source reference.
- Source references are credential-free logical/opaque references, not embedded raw provider endpoints.
- Reject secret-bearing/credential/endpoint fields recursively and reject credential-like query fragments.
- External-source fixture demonstrates wiki/api/vector-store style reference without credentials.
- Local/offline fixture demonstrates repository/file knowledge.
- No network access during parse/validation.

## Acceptance criteria
- [ ] versioned JSON schemas checked in.
- [ ] valid change chain parses and validates.
- [ ] unapproved/stale change plan blocks chain.
- [ ] configuration delta forbids secret values and requires release + rollback links.
- [ ] release evidence is reachable from configuration delta summary.
- [ ] local domain-knowledge descriptor parses.
- [ ] external-source descriptor parses without provider credentials/endpoints.
- [ ] forbidden credential/endpoint fields fail closed without echoing secret values.
- [ ] descriptors remain references only.
- [ ] at least two executable offline samples added.
- [ ] full repository verification passes.

## Focused verification
- uv run pytest -q tests/test_change_management.py tests/test_domain_knowledge.py tests/test_templates.py
- uv run ruff check src/agora_ai_sdlc/change_management.py src/agora_ai_sdlc/domain_knowledge.py tests/test_change_management.py tests/test_domain_knowledge.py
- uv run ruff format --check src/agora_ai_sdlc/change_management.py src/agora_ai_sdlc/domain_knowledge.py tests/test_change_management.py tests/test_domain_knowledge.py

## Full verification
- uv run python scripts/verify_all.py

## Dependencies
#105 is merged to main.

## Scope boundary
These contracts record and validate governance metadata. They do not fetch domain content, execute deployment/configuration mutation, call provider APIs, or replace Core lifecycle authority.

## Completion evidence
- TESTS.md
- RESULT.md
- independent REVIEW.md before merge
