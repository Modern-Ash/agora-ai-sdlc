# Public AWS AI-DLC concept mapping

Source: the public AWS DevOps Blog post "AI-Driven Development Life Cycle" (`https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/`). Only publicly described phase and concept names are compared. No proprietary prompts or text are reproduced. AWS is methodological inspiration, not a runtime dependency or endorsement.

| Public AI-DLC concept | Agora AI-SDLC construct | Notes |
|---|---|---|
| Inception phase | `inception` lifecycle state | Gate `architecture-approved` |
| Construction phase | `construction` lifecycle state | Gate `build-verified` |
| Operations phase | `operations` lifecycle state | Gate `completion` |
| Unit of Work | [Unit of Work](../terminology.md) | Bounded deliverable in the lifecycle |
| Bolt | [Bolt](../terminology.md) | Iteration over a Unit of Work; no time tracking in Core |
| AI proposes, human validates | Clarification plus accountable-role approval | Enforced by Core gates, not by convention |

Agora additions with no counterpart claimed here: `readiness` and `intent` states, evidence-based gates, producer/reviewer separation, data-eligibility and provenance policies, profiles.
