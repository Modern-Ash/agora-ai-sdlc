# ADR-0002: No embedded LLM SDK

- Status: accepted
- Date: 2026-09-20
- Deciders: Modern Ash maintainers
- Related issues: #12

## Context

Runtimes, providers and models change quickly and differ per customer. Credentials must never be persisted by this project.

## Decision

The flavor depends only on Agora Core and development tooling. Runtimes are external, replaceable actors described by provider-neutral metadata. Model names never imply provider independence.

## Alternatives considered

- Bundle one provider SDK: creates lock-in and credential handling.
- Optional SDK extras: still couples releases to providers.

## Consequences

Provenance is declared and validated, not executed. Runtime adapters live outside this repository.
