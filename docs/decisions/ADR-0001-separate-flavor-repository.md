# ADR-0001: Separate flavor repository

- Status: accepted
- Date: 2026-09-20
- Deciders: Modern Ash maintainers
- Related issues: #12, #11

## Context

Agora Core serves several methods (Scrum, Kanban, Spec-Driven Development). AI-SDLC is one opinionated method.

## Decision

AI-SDLC lives in `Modern-Ash/agora-ai-sdlc` as a flavor that consumes Core through its released compatibility range. Generic primitives go to Core; see [repository boundaries](../repository-boundaries.md).

## Alternatives considered

- Embed the method in Core: couples Core releases to one method.
- Embed in Studio: Studio must not parse Method Packs or write `.agora/`.

## Consequences

Core changes needed here require an upstream issue and a released boundary. The flavor never duplicates lifecycle logic.
