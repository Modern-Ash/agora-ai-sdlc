# Context graph

Persisted artifacts already trace to each other through `traces-to`. The context graph turns that into the minimal, deterministic context an agent needs for one Intent, Unit, artifact or Bolt. It reads files only: no vector database, network or provider.

## Nodes and edges

- Every artifact is a node; `traces-to` gives its **backward** edges (sources). **Forward** is the inverse.
- Every Bolt in a `bolt-plan` is a node addressed `BLP-001/bolt-id`. A Bolt traces back to its plan and to the Bolts it depends on, and each artifact it `produces` traces back to the Bolt. This makes Unit → Bolt → artifact navigable in both directions.

## Selection rules

- Backward and forward traversals are independent, so sibling Units and unrelated branches are never included.
- Items are ordered by distance, then backward before forward, then artifact-kind order, then id. The same files always give the same bundle.
- `--depth N` limits distance. `--max-tokens N` keeps items in order while they fit (about four characters per token); larger items are listed as `omitted`, never truncated. The root is always kept.
- Cycles terminate and are reported; dangling links are reported for the selected nodes only. `--strict` turns either into an error (`context.cycle`, `context.dangling`).

## CLI

```
agora-ai-sdlc context DIR ID [--direction backward|forward|both] [--depth N] [--max-tokens N] [--strict] [--content] [--json]
```

`DIR` holds artifact documents (non-artifact Markdown is ignored; an invalid artifact fails with `context.artifact`). `ID` is an artifact id or `BLP-001/bolt-id`. Read-only.

## Brown-field semantic elevation

`static-system-model` (`SSM`) and `dynamic-system-model` (`DSM`) elevate a legacy inventory into components/relationships and observed behavior. `agora_ai_sdlc.semantic_elevation` validates that both exist for the work and are linked; `plan-validate --artifacts DIR` applies it when the pathway policy requires it (see [adaptive planning](adaptive-planning.md)).
