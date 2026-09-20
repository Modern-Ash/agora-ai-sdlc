# Flavor manifest reference (`agora/flavor/v1`)

File: `src/agora_ai_sdlc/flavor/flavor.yaml` (packaged as `agora_ai_sdlc/flavor/flavor.yaml`). Implementation: `agora_ai_sdlc.flavor_manifest`. Validation is local, deterministic and performs no network access.

## Normative fields

| Field | Type | Rule |
|---|---|---|
| `schema` | string | Must equal `agora/flavor/v1`; other values fail with `manifest.schema` (including future versions). |
| `id` | string | `^[a-z][a-z0-9-]*$` |
| `name` | string | Non-empty |
| `version` | string | Semantic version (`MAJOR.MINOR.PATCH[-pre][+build]`, no leading zeros) |
| `supported_core` | string | PEP 440 specifier set for Agora Core, e.g. `>=0.8.2,<0.9` |
| `method_packs`, `profiles`, `policies`, `required_capabilities` | list of strings | Optional, default empty; duplicates rejected |

## Presentation metadata

`metadata` (mapping) is presentation-only and never affects validation or behavior. Any other unknown top-level field is rejected (`manifest.unknown`).

## Error codes

`manifest.syntax`, `manifest.schema`, `manifest.missing`, `manifest.unknown`, `manifest.type`, `manifest.id`, `manifest.version`, `manifest.core_range`, `manifest.duplicate`, `manifest.core_incompatible`, `manifest.core_version`. Codes prefix every message and are stable; message text may change.

## Compatibility check

`check_core_compatibility` compares the installed `agora-framework` version to `supported_core` and, on failure, names both: `installed Core 0.9.0 is outside supported range >=0.8,<0.9`.

## Notes

The manifest is a local product contract; no generic flavor concept is added to Core. Parsing uses PyYAML `safe_load`.
