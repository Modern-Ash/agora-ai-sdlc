# Model Provenance Policy

Model provenance records describe the runtime, provider, model and selection reason used by an actor. Values are either `observed`, `declared` or `unavailable`; unavailable values never count as distinct for independence checks.

The policy is vendor-neutral: local and internal providers are valid, model names never imply provider identity, and records must not contain credentials, tokens or endpoint URLs.

The deterministic reference implementation is `agora_ai_sdlc.provenance`.
