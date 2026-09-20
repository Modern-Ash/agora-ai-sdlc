# Model Provenance Policy

Model provenance records describe the runtime integration, runtime version, provider, model, selection reason and fallback used by an actor. Each value is `observed`, `declared` or `unavailable`. Fallback has the same source marker; when used, it identifies the original runtime, provider and model plus a reason.

Unknown or insufficiently trusted provenance never counts as distinct. Comparisons normalize case and surrounding whitespace and return `same`, `distinct` or `unknown` for actor, runtime, provider and model. Policy evaluation fails closed with a blocker that names the dimension and whether it is the same or unknown.

The schema is vendor-neutral. Local and internal providers are ordinary provider strings, and model names never imply provider identity. Records reject credential-like fields and values, including tokens, authorization headers, private keys and endpoint URLs. Errors do not echo rejected values.

## Agora Core Mapping

| Provenance field | Agora Core 0.8.2 source | Trust |
| --- | --- | --- |
| actor | `SessionRecord.executor`, falling back to accountable `actor` | Core session identity |
| runtime | `SessionRecord.integration` | declared |
| provider | `SessionRecord.provider` | declared |
| model | `SessionRecord.model` | declared |
| runtime version | not persisted on sessions | unavailable |
| selection reason | not persisted on sessions | unavailable |
| fallback actually used | configured fallbacks exist on actors, but actual selection is not persisted on sessions | unavailable |

`from_core_session` performs this mapping without changing Core state. `from_core_usage` follows `UsageRecord.session_id` to the authoritative session instead of copying provenance into a shadow usage or session store. A usage record without a resolvable session fails closed.

The missing generic session fields are tracked upstream in [Agora Core #54](https://github.com/Modern-Ash/agora/issues/54). Until a released compatibility boundary provides them, this distribution records them as unavailable and does not infer them from commands, model names or configured fallback lists.

The deterministic reference implementation is `agora_ai_sdlc.provenance`.
