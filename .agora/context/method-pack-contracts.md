---
sources: [issues #11, #13, #15-#20]
status: draft
---
# Method Pack contracts

- Flavor manifest schema id `agora/flavor/v1`: id, name, distribution version, supported Core range, method packs, profiles, policies, required capabilities; strict unknown-field handling; semver validation; no network access (#11).
- Method Pack at `registry/methods/ai-sdlc/` (`METHOD.md`, `PROTOCOL.md`, `TOOLS.md`): declares states, initial/terminal state, rework edges, roles, outputs and stopping conditions per phase; provider-neutral capabilities only (#13).
- Every gate needs positive and negative automated tests (#2).
- These paths are planned; do not assume they exist until the issue lands.
