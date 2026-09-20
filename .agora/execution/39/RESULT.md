---
issue: 39
status: implemented
commit: pending
pull_request: pending
updated_at: 2026-09-20
---
# Result: Single-command AI-SDLC conformance harness

## Status

Implementation and verification complete; independent review pending.

## Concise summary

Added `agora-ai-sdlc self-test`, a packaged, credential-free conformance command that discovers all shipped assets, executes every sample, exercises AI-SDLC roles through real Agora Core APIs, and emits a schema-versioned result.

## Files modified

New conformance package, JSON result schema, tests, and reference guide; CLI, repository verification, testing docs, and README updated.

## Decisions made

- Reused packaged asset roots and existing profile loaders instead of duplicating behavior in the harness.
- Exercised service actors as fail-closed negative cases because no current AI-SDLC role permits them.
- Used a represented child swarm for supported delegated role holders.
- Captured sample stdout internally so `--json` reserves stdout for one machine-readable result; progress uses stderr.
- Retained failed harness workspaces but cleaned successful and interrupted runs, restoring caller `AGORA_HOME` in every path.

## Criteria satisfied

- One command verifies the Method Pack, profiles, policies, templates, contracts, role paths, and every executable sample.
- Caller working directory and environment remain unchanged.
- Failure returns structured diagnostics and a retained path; success/interruption clean up.
- The normal package verification installs the wheel and runs its complete self-test.
- Deterministic tests cover success, injected failure, interruption, output contract, streams, and exit codes.

## Tests run

Focused conformance/CLI/verification tests, Ruff, direct CLI execution, full repository verification, and wheel-installed self-test.

## Results

Focused: `10 passed`; strengthened interruption suite: `4 passed`. Full: `517 passed, 2 skipped`; all phases passed. Direct self-test: 13 checks passed.

## Deviations

None from issue scope. The command validates offline contracts and scenarios; it does not claim live-provider conformance.

## Remaining risks

An operating-system kill that prevents Python `finally` blocks may leave a temporary directory. Live integrations and provider behavior remain outside this offline harness.

## Pending work

Independent review, PR creation, and repository CI.

## Commit and pull request

Pending.
