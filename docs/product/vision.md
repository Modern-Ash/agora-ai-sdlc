# Product vision

Agora AI-SDLC is Modern Ash's vendor-neutral distribution of AI-first software-delivery practice on [Agora Core](../repository-boundaries.md). AI actors fill delivery roles, alone or paired with humans, while accountability stays with a named human role holder. Every claim is limited to what the repository implements; scope is in [product-scope](../product-scope.md).

## Outcomes

- Work moves through a lifecycle only with recorded evidence and approvals; missing metadata fails closed.
- Any runtime, provider or model can be swapped without changing the method.
- Markdown and Git remain the project source of truth; nothing requires a hosted service.

## Non-goals

No embedded LLM SDK, cloud dependency, lifecycle engine, or compliance/certification claim ([ADR-0002](../decisions/ADR-0002-no-embedded-llm-sdk.md)).

See [architecture](../architecture.md) and [terminology](../terminology.md).
