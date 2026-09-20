# ADR-0003: Provider-neutral naming

- Status: accepted
- Date: 2026-09-20
- Deciders: Modern Ash maintainers
- Related issues: #12

## Context

Method vocabulary borrowed from a vendor would imply dependence on, or endorsement by, that vendor.

## Decision

Use one canonical, independent term per concept ([terminology](../terminology.md)). Vendor names appear only where attributing inspiration or in clearly illustrative mappings.

## Alternatives considered

- Adopt vendor names verbatim: implies affiliation.
- Per-provider dialects: fragments the method.

## Consequences

A terminology test rejects vendor-derived names outside the allowed attribution files.
