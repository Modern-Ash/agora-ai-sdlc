# Independent Review Policy

Issue #22 defines producer/reviewer separation as a local policy contract for the AI-SDLC distribution. Agora Core remains the lifecycle authority; this repository does not add a parallel gate engine. Callers evaluate this policy before recording Core approval or evidence.

## Profiles

| Profile | Rule |
| --- | --- |
| `distinct-actor` | Reviewer actor identity must differ from the producer actor identity. |
| `distinct-runtime` | Reviewer runtime must differ from the producer runtime. |
| `distinct-provider` | Reviewer provider must differ from the producer provider. |
| `human-final` | Final review must be performed by a human actor. |
| `regulated` | Requires a distinct actor identity, observed `distinct-provider` and human final review. Human final review cannot be waived. |

Profiles compose by union: all required dimensions and human-review requirements must pass. Unknown provenance is never independent.

## Artifact Binding

Critical artifacts declare `separation-policy` in front matter. Producer provenance and review both bind to the artifact kind, id, revision and digest. Any new artifact revision or content digest invalidates prior review and requires new production provenance and review records.

Critical artifact kinds are requirements, architecture, threat model, test strategy, implementation plan, deployment plan, rollback procedure and operational readiness.

## Waivers

Where the active profile permits a waiver, the waiver must include:

- `actor`
- `reason`
- `evidence`

Only `governance-owner` can authorize waivers. Unauthorized or incomplete waivers fail closed and do not clear policy blockers. In the regulated profile, required human final approval is non-waivable.

## Verification

The deterministic reference implementation is `agora_ai_sdlc.independent_review`. It covers profile composition, stale review detection, waiver authorization and regulated human-final behavior without network, LLM credentials or provider SDKs.
