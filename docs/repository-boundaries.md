# Repository boundaries

> If a capability serves Scrum, Kanban, Spec-Driven Development or other methods, it belongs in **Agora Core**. If it expresses how Modern Ash implements AI-SDLC, it belongs in **Agora AI-SDLC**.

| Change | Owner |
|---|---|
| AI-SDLC Method Pack, protocol, role matrix | This repo |
| Depth and adoption profiles, policy profiles, sample scenarios | This repo |
| Flavor manifest parser for `agora/flavor/v1` | This repo |
| Product docs, service offer, reference architecture | This repo |
| New generic enforcement primitive (e.g. new gate type, reviewer-separation engine) | Agora Core, consumed here after a released compatibility boundary |
| Lifecycle engine, transactions, durable-state format | Agora Core |
| Dashboard, clarification queue UI, provenance views | Agora Studio |
| Multi-user auth, tenancy, hosted registry, SaaS | Future Control Plane |

Rules: Studio must not parse Method Packs or write `.agora/` directly; this repo must not duplicate Core lifecycle logic or embed LLM SDKs. When ownership is unclear, open a clarification and, if durable, an ADR.
