# Studio projection contract

`ai-sdlc-projection-v1.schema.json` is the proposed cross-repository read contract owned by issue #36. It is a consumer contract, not evidence that current Agora Core or Agora Studio releases implement the aggregate.

Fixtures:

- `complete.json`: every projection is available and backed by an identified source schema.
- `unavailable.json`: every missing projection has an explicit stable reason.
- `future-state.json`: unknown state ids, source-schema revisions and additive fields remain generically renderable.

Normative behavior, field ownership and compatibility are documented in [Studio projection](../../docs/integrations/studio-projection.md).
