# Agora Studio projection contract

## Purpose

The AI-SDLC Studio projection is a read-only, versioned consumer contract between Agora Core, this flavor and Agora Studio. It lets Studio render AI-SDLC state without parsing Method Pack, profile, policy or artifact Markdown and without becoming a lifecycle authority.

The proposed schema is [`agora-ai-sdlc/studio-projection/v1`](../../contracts/studio/ai-sdlc-projection-v1.schema.json). Its fixtures are contract examples, not claims that current Core or Studio releases already expose the aggregate.

## Transport boundary

The browser request contains only a server-issued opaque `selection_id` plus validated logical `swarm_id` and `work_id` values. A trusted loopback host selects or opens the local project through startup configuration, CLI/native interaction, or another non-browser boundary and maps it to the opaque id. The browser never sends, receives, reconstructs or stores an absolute project path.

Core application services produce durable read DTOs. A Core-owned aggregation boundary combines those DTOs with installed flavor projectors. Studio consumes normalized JSON only. Studio must not read `.agora/`, import flavor internals, parse flavor Markdown, infer provider identity, recalculate policy decisions, or turn presentation hints into authority.

The response identifies the logical project, swarm, work and a SHA-256 snapshot. It never includes credentials, private keys, provider endpoints, prompts, model reasoning or filesystem paths.

## Sections and authority

| Section | Authority | Current source or gap |
| --- | --- | --- |
| `flavor` | Installed flavor metadata selected by Core | `agora/flavor/v1` exists in this package; Core 0.8.2 does not project active flavor metadata |
| `profiles` | Active profile configuration resolved by the flavor through Core's extension boundary | Profile manifests exist; no active-profile durable/read contract exists in Core 0.8.2 |
| `lifecycle` | Agora Core | Core `agora/application/lifecycle-projection/v3` already supplies dynamic states, transitions, gates and blockers |
| `clarifications` | Agora Core | Core traceability v2 carries clarifications, but the aggregate needs stable normalized clarification entries |
| `provenance` | Core sessions plus the flavor's provenance policy | Work-scoped executions remain linked by session id; Core session v1 has actor/integration/provider/model only; [Core #54](https://github.com/Modern-Ash/agora/issues/54) tracks the missing neutral fields |
| `separation` | Flavor policy evaluated from Core actor/session/artifact facts | `independent-review/v1` exists here; no generic Core extension projection transports its decision |
| `metrics` | Core facts normalized by the flavor | Core exposes counts, activity, evidence and usage; no AI-SDLC metric-window aggregate exists |
| `presentation` | Flavor hints only | Explicitly `authoritative: false`; labels and order may be ignored by Studio |

Lifecycle state ids are open strings. Studio renders an unknown id using its literal safe text and generic visual treatment. It must not map unknown states to a known state, hide them, or use a hard-coded AI-SDLC transition list.

## Availability

Every projection section is required in the envelope. An available section contains `status: available` and `value`. A missing, unsupported or inapplicable section contains `status: unavailable` and a stable `reason.code` plus safe human-readable message; it does not use `null`, `{}`, an empty list or omission to mean unknown.

Availability is not success. For example, an available separation projection may have `decision: blocked`, and available lifecycle data may contain blockers. Studio displays the projected decision and never weakens it.

## Versioning

The top-level schema id versions the aggregate independently from nested source schemas. Within v1:

- producers may add fields and sections;
- consumers must ignore unknown additive fields while preserving every required v1 field;
- lifecycle state ids, profile ids, metric ids and decision values are extensible strings;
- a missing required section or malformed availability envelope is incompatible;
- changing meaning, removing a required field or changing a field type requires v2;
- nested `source_schema` identifies the authority used to produce that section and is diagnostic, not an instruction for the browser to fetch or parse another resource.

Consumers may continue to render sections whose known required fields are valid when another section is explicitly unavailable. They must fail the aggregate closed on an unsupported top-level major version, missing required section, project identity mismatch, malformed snapshot or contradictory lifecycle identity.

## Compatibility

| Component | Version | Contract status |
| --- | --- | --- |
| Agora AI-SDLC | 0.1.x | Publishes projection v1 requirements, schema and fixtures and provides the provider `agora_ai_sdlc.studio_projection:projector` |
| Agora Core | 0.9.0 | Provides the generic flavor projection boundary (`AgoraReadService.flavor_projection`), clarification projection and session provenance; lifecycle v3 and traceability v2 remain the sources |
| Agora Core | 0.8.2 | Partial sources only: no aggregate or extension boundary; the provider module imports but cannot project |
| Agora Studio | 0.6.0 | Consumes projection v1 with opaque `selection_id`; loads a provider only from startup configuration (`--flavor-projector`) |

The provider fills `flavor` from the packaged manifest and `provenance` from Core session provenance (bases stay `declared`; nothing is upgraded to `observed`). `profiles`, `separation` and `metrics` are explicit `unavailable` sections because Core does not yet transport active-profile, reviewed-artifact or metric-window facts to a flavor. Run Studio with:

```console
agora-studio --project <path> --flavor-projector agora_ai_sdlc.studio_projection:projector
```

### Presentation profiles

The same work item can be presented through a compatibility profile without changing Core state: `:aws_original_projector` (3 stages) or `:lg_enterprise_projector` (Initialization, Ideation, Inception, Construction, Operation). The profile (`profiles/compatibility/<id>/profile.yaml`, versioned) maps canonical states to stages; the projector then adds `presentation.stages` (profile id/version, current stage, done/current/upcoming per stage) and relabels `presentation.labels`. These are additive, non-authoritative hints; the default `:projector` is unchanged. See `agora_ai_sdlc.presentation`.

Compatibility is asserted only after tests in each owning repository pass against these exact fixtures. A future Core or Studio version is not compatible merely because its version is newer.

## Verification responsibilities

This repository verifies that fixtures contain all sections, unavailable values are explicit, unknown future states and additive fields remain valid, presentation is non-authoritative, references resolve locally, and browser-visible data contains no filesystem paths or credential-shaped values.

Core must add producer tests using real application services, snapshot consistency tests, unavailable-source tests and backward/forward fixture tests; that gap is [Core #55](https://github.com/Modern-Ash/agora/issues/55). Studio must add strict envelope tests, generic unknown-state rendering, per-section unavailable states, stale-refresh behavior, path-free requests, no-Markdown-parser boundary checks, and Chromium coverage; that gap is [Studio #10](https://github.com/Modern-Ash/agora-studio/issues/10). Those implementations belong to their owning repositories and are linked from issue #36.
