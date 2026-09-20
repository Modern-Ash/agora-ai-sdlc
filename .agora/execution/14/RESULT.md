---
issue: 14
status: partial
pull_request: pending
---
# Result
verify_all.py, CI workflow (PR + main, 3-version matrix, uv cache, log artifact only on failure), CONTRIBUTING, SECURITY, ruff config, doc updates (AGENTS.md section 7, testing.md, context).

## Deviations
- Packs/samples phases are placeholders that say so explicitly until #13/#21; the `agora pack validate` invocation is untested.
- Link check is local-only (no external URLs).
- SECURITY.md assumes GitHub private vulnerability reporting is enabled (unverified).
- "Package built from wheel" implemented; ruff added as dev dependency.
