---
issue: 32
status: implemented
implemented_at: 2026-09-20
implementer: Codex
review: pending-independent
---
# Result: Starter profile and guided bootstrap

## Outcome

Added a preview-first Starter profile that bootstraps one fresh or existing repository, one accountable team, the exact shipped AI-SDLC pack, and the first Unit of Work using supported Agora Core APIs.

## Delivered

- Starter adoption manifest with standard depth, one-team topology, two-runtime maximum, and upgrade paths.
- Pure deterministic preview plus interactive confirmation and explicit `--yes` automation.
- Distinct human Product Owner and Quality Reviewer with human or declared runtime execution roles.
- Exact `ai-sdlc@0.1.0` snapshot installation and post-install version check.
- Credential-free executable sample, CLI command, tests, and operating documentation.

## Acceptance evidence

- Fresh and existing Git repository tests both validate; existing files remain unchanged.
- Cancellation creates neither target nor Agora home.
- Explicit config produces repeatable preview and non-interactive bootstrap.
- Core validation passes and the first work item is in `readiness`.

## Limits

- Starter does not configure credentials, install CLIs, launch runtimes, or provide shared/remote governance.
- Standard depth is an AI-SDLC adoption obligation profile; Core lifecycle enforcement remains owned by the installed Method Pack.
- Independent review remains pending.

## Verification

Focused checks: `13 passed`; Ruff passed. Full verification: `430 passed, 2 skipped`; all phases passed with eight samples and wheel smoke test.
