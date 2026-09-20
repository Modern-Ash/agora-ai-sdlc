# Multi-Runtime Conformance

The default conformance matrix is offline and credential-free. It launches adapter-shaped fake processes through real Agora Core sessions, persists real Core session summaries, registers normalized artifacts and evidence, and evaluates AI-SDLC data, review and runtime-selection policies.

## Coverage

| Combination | CI status | Meaning |
| --- | --- | --- |
| Codex to Claude | contract-tested with fake structured runners | Core integration metadata and normalized lifecycle semantics are exercised; no live provider call |
| Claude to Codex | contract-tested with fake structured runners | Same as above in reverse order |
| local/generic to Codex | contract-tested with fake structured runners | Generic runner compatibility plus Codex integration metadata |
| same-provider, distinct actor | contract-tested pass/fail policy case | Actor separation passes while runtime/provider separation fails |
| human review | contract-tested pass/fail policy case | Human-final and regulated profiles pass with observed fake provenance |
| same actor | negative policy case | Self-review is rejected even across different providers |

Codex and Claude are tested adapter contracts, not live-provider claims. The `generic` integration is compatibility for a caller-supplied command. Ollama and OpenCode may be used through a generic runner, but this repository does not claim native adapter support or live conformance for them.

All provider-shaped output is normalized to outcome, phase, artifact and token fields before cross-runtime assertions. The matrix compares a checked-in snapshot of sessions, evidence and work state, so provider-specific envelope details cannot change lifecycle expectations.

Run the deterministic matrix with:

```console
uv run pytest tests/conformance/runtimes/test_matrix.py -q
```
