---
issue: 11
status: complete
pull_request: pending
---
# Result
Manifest v1 parser/validator, packaged flavor.yaml and FLAVOR.md, reference doc, tests.

## Decisions / assumptions (public schema)
- YAML parsing via PyYAML and version ranges via `packaging` (two new runtime dependencies; Core uses neither).
- `supported_core` is a PEP 440 specifier set; `version` is semver.
- Only `metadata` is presentation; any other unknown field is rejected.
- Files live under `src/agora_ai_sdlc/flavor/` (not top-level `flavor/`) so they load identically from source and wheel.
- Lists in the shipped manifest are empty: no profiles, policies or capabilities exist yet.

## Risks
Independent review pending.
