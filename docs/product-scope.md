# Product scope

Scope statements derive from epics #1–#8; GitHub remains the detailed source.

## MVP (M0–M1)

- Repository foundation, flavor manifest, packaging, verification pipeline (epic #1).
- AI-SDLC Method Pack: lifecycle, roles, gates, templates, depth profiles, credential-free sample (epic #2).
- GitHub and generic CI evidence profiles for the first pilot (epic #4).
- Single-user, local approvals, CLI-first usage.

## Post-MVP

Multi-LLM governance policies (#3), GitLab/Jira/observability profiles, Enterprise/Modernization/Regulated profiles, Studio projections, pilots and conformance harness, service offer (M2–M6).

## Out of scope now

Multi-user or SaaS features, the Control Plane (M7), provider credentials, direct LLM SDK integration, AWS runtime requirements, duplicating Core logic, unevidenced compliance or certification claims.

## External dependencies

A compatible Agora Core release; Agora Studio for its epic; GitHub for the first integration profile.

## Assumptions to validate

- Core exposes the capabilities the Method Pack needs without upstream changes.
- Two runtime combinations can run one scenario offline.
- The context budgets in [token-efficiency](development/token-efficiency.md) are workable for typical issues.
