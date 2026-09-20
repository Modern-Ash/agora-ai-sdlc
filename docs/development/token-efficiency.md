# Token efficiency

Practices: versioned stable context in `.agora/context/`; small Task Packets; summaries that record their source commit; diff-based review; disposable per-issue sessions; focused tests during development and the full suite before PR/merge; split oversized tasks before implementing.

| Task type | Input | Output |
|---|---:|---:|
| Simple documentation | 5k–10k | 2k–5k |
| Template or manifest | 8k–15k | 3k–6k |
| Focused implementation | 15k–30k | 5k–12k |
| Cross-cutting/Core change | 30k–50k | 8k–20k |
| PR review | 10k–20k | 3k–8k |
| Architecture analysis | 20k–40k | 5k–12k |

These are guidance, not provider guarantees. A task expected to exceed its budget must be split first. Labels `context:small|medium|large` express the estimate.
