# Terminology

One canonical term per concept. Extend this file, do not fork definitions elsewhere.

| Term | Definition |
|---|---|
| AI-SDLC | The AI-first delivery method implemented by this flavor. |
| Agora Core | Generic governance/lifecycle engine (`Modern-Ash/agora`). |
| Flavor | A distribution of Method Pack, policies, profiles and templates on Core. |
| Method Pack | Declarative lifecycle, roles, protocol and tools installed into Core. |
| Actor | An entity performing work: human, AI runtime, or service. |
| Role | Named authority/capability set held by an actor. |
| Runtime | The agent product/harness executing an AI actor (e.g. a CLI agent). |
| Provider | The organization/service hosting a model. |
| Model | The specific LLM used by a runtime. Model names never imply provider independence. |
| Swarm | A governed group of actors working on shared work items. |
| Unit of Work | Bounded deliverable moving through the lifecycle. |
| Bolt | Short iteration cycle over a Unit of Work, without time tracking in Core. |
| Gate | Checkpoint requiring evidence/approval for a transition. |
| Evidence | Recorded, verifiable proof (tests, reviews, approvals) attached to a gate. |
| Profile | Opinionated adoption/policy configuration (Starter, Enterprise, Modernization, Regulated). |
| Task Packet | The minimal context bundle for one issue: `TASK.md` plus referenced files. |
| Clarification | Recorded question resolved by the accountable human before execution. |
| Studio | Agora Studio (`Modern-Ash/agora-studio`): UI projections of Core state; holds no lifecycle policy. |
| Control Plane | Future multi-user/enterprise service; not part of the MVP. |
| Execution folder | `.agora/execution/<issue>/`, per-issue working artifacts. |

Deprecated: the former dotted repository name (use `agora-ai-sdlc`).
