---
issue: 36
status: contract-implemented
implemented_at: 2026-09-20
implementer: Codex
review: pending-independent
upstream_core: Modern-Ash/agora#55
upstream_studio: Modern-Ash/agora-studio#10
---
# Result: cross-repository AI-SDLC projection contract

## Outcome

Published the proposed `agora-ai-sdlc/studio-projection/v1` read contract, complete/unavailable/future-state fixtures, ownership map and compatibility table. The contract is packaged in both wheel and source distributions.

## Decisions

- Browser requests use an opaque server-issued selection id plus logical swarm/work ids, never filesystem paths.
- Every projection section is present and explicitly available or unavailable.
- Lifecycle and policy ids are open strings; additive fields remain compatible within v1.
- Work-scoped provenance is a list of session-linked executions with structured fallback facts.
- Core remains lifecycle/snapshot authority; flavor policies own separation and normalization; presentation hints are never authoritative.
- Nested source schemas identify authority but do not instruct Studio to parse another resource.

## Acceptance evidence

- Fixtures demonstrate blocked lifecycle state, open clarifications, complete provenance, separation blockers, Core-backed metrics, wholly unavailable data and an unknown future state.
- Tests reject implicit missing sections and scan all browser-visible fixtures for filesystem paths and credential-shaped data.
- Studio requires normalized JSON only; the contract contains no Markdown or file-reading instruction.
- Current support and gaps are mapped for Core 0.8.2, Studio 0.5.0 and future unreleased implementations.

## Remaining work

- Core #55 must implement the generic flavor aggregation/application-service boundary and real producer compatibility tests.
- Core #54 must complete provider-neutral session provenance.
- Studio #10 must implement path-free selection, consume the aggregate and add compatibility, Chromium, accessibility and viewport tests.
- AI-SDLC #36 remains open until owning-repository PRs are linked and verified; this PR must use `Refs #36`, not close it.
- Independent review remains pending.

## Verification

Focused checks: `30 passed`; Ruff, format and JSON parsing passed. Full verification: `510 passed, 2 skipped`; all phases passed, including isolated wheel contract discovery.
