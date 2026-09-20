---
sources: [issues #1, #2, #12]
status: draft
---
# Product contracts

- Distribution is vendor-neutral: no AWS, Amazon Q, Kiro, Bedrock or model-provider requirement.
- Ownership split between Core, flavor, Studio: [repository-boundaries](../../docs/repository-boundaries.md).
- Lifecycle: `readiness -> intent -> inception -> construction -> operations -> completed`; rework edges `inception -> intent`, `construction -> inception`, `operations -> construction`; post-completion changes create a new revision.
- Missing evidence, unresolved clarification or missing approval fail closed.
- No credentials or provider SDK dependency in the repo.
- Public AI-DLC concepts are attributed; branding is independent; no endorsement or certification claims.
