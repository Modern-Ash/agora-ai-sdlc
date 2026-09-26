# Adding a new agent runtime

The pipeline every runtime plugs into:

```text
Core authority
 -> deterministic AI-SDLC
 -> optional Laya advisory plane
 -> ExecutionRequirements
 -> deterministic runtime admission
 -> RuntimeBinding
 -> RuntimeAdapter
 -> agent/model execution
 -> evidence reconciliation
 -> Core
```

Workflow code never branches on a provider name. Follow these steps in order.

1. **Runtime type.** Decide whether it is an *agent runtime* (repository-aware host: Claude Code, Codex, OpenCode) or a *model runtime* (serves models only: Ollama). A model runtime never executes on its own; bind it to an agent (`RuntimeBinding(agent, model)`). See `runtime_domain.py`.
2. **Capability manifest.** Register a manifest in `agent_capabilities.py` with `build_manifest`, claiming every capability id explicitly. Claim only what the adapter implements and a test proves; unsupported is the default (`isolated_reviewer` is false everywhere today).
3. **Discovery.** Add the CLI to `RUNTIME_CANDIDATES` in `runtime_discovery.py`. Discovery is credential-free (`--version` only) and reports observed facts; never mix it with the static manifest.
4. **Adapter.** Subclass `RuntimeAdapter` in `<name>_adapter.py` (`integration_id` = manifest agent id) and implement only `health`, `plan_projection` and `render_invocation`; optionally `parse_output`. Use `probe_health` for version diagnostics. Verify every flag against the real CLI's `--help` and record the verified version in the module docstring.
5. **Projection.** Return `ProjectionEntry` items (marked text blocks or named JSON keys). Never write credentials; keep unrelated user configuration intact; report surfaces you do not project through `unsupported_surfaces`.
6. **Execution.** `render_invocation` receives a verified `ExecutionEnvelope` and must return a `PreparedExecution` with the same digest, operation and arguments. Model assignment: use the native mechanism only for explicit, safe ids; never invent a model, never pull one.
7. **Conformance.** Add the adapter to `tests/support/runtime_scenarios.py` (fake probe, binding) and to the parametrized `tests/test_runtime_conformance.py`; write adapter-specific tests for health, projection, model assignment and output parsing. Register it in `adapters.py`.
8. **Docs.** Add a section to `docs/architecture.md` naming the verified CLI version, native surfaces used and explicit non-claims.

Rules that must hold: Core is the only lifecycle authority; adapters transport and project, they do not choose Work, transitions, approvals or fallbacks; runtime output is evidence for reconciliation, never authority.

## Migrating existing runtime configuration

`aisdlc runtimes --migrate-preview` prints the deterministic `runtime-binding/v2` form of every runtime entry in `ai-sdlc/project.yaml` and of legacy Core actor metadata, and never writes. Ambiguous entries (for example Ollama declared as an agent host) get a typed diagnostic (`runtime.legacy_model_runtime_as_agent`, `runtime.legacy_partial_model`, ...) instead of a guess. Compatibility window: v1 flat entries remain readable, `select_runtime` keeps the flat v1 fields in `selected` and adds `binding`, and `aisdlc runtimes --json` keeps its fields and adds `kind` and `models`. `aisdlc runtimes --diagnose` shows agent/model runtime, capabilities, binding status, adapter and projection sync state.

## Attribution boundary

The runtime-adapter architecture is informed by public patterns observed in Gentle-AI (capability manifests, provider-native projections, exact machine transitions, immutable review subjects). Agora does not depend on Gentle-AI, does not use ODD, RDD or Engram, owns its contracts and implementation, and keeps Agora Core as the sole lifecycle authority.
