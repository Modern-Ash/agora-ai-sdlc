---
issue: 38
status: implemented
commit: pending
pull_request: pending
updated_at: 2026-09-20
---
# Result: Existing-codebase multi-LLM pilot

## Status

Implementation and verification complete; independent review pending.

## Concise summary

Added a credential-free existing-codebase pilot that launches adapter-shaped fake workers through real Core sessions, rejects an incomplete change, replaces the producer provider, approves the correction independently, records current-commit CI evidence, and completes the AI-SDLC lifecycle.

## Files modified

New pilot fixture, runner, executable scenario, test, guide, and issue execution records; sample index updated.

## Decisions made

Used a Python standard-library catalog as the issue's permitted maintained equivalent to Java/Spring Boot. Kept all provider behavior fake and deterministic while exercising real Core session and lifecycle APIs. Used distinct actor/provider review policy and retained human QA approval for the Core gate.

## Criteria satisfied

- Provider-alpha is replaced by provider-beta without changing the installed Method Pack digest.
- Exact-revision producer/reviewer provenance exposes actor, runtime, provider, and model.
- The first review is `changes-requested`; operations blocks until correction, verification, CI evidence, and approval.
- Baseline and result measurements are separate from unmeasured production/live-provider expectations.
- Source and installed-wheel executions both complete and validate.

## Tests run

Focused sample and runtime matrix tests, Ruff lint/format, direct source sample, full repository verification, and installed-wheel sample.

## Results

Focused: `8 passed`. Full: `511 passed, 2 skipped`; all verification phases passed with eleven samples. Wheel-installed pilot completed with `validate: ok`.

## Deviations

No live providers were called. Offline CI observations are bounded fixtures; only local test outcomes and orchestration state are measured facts.

## Remaining risks

Live provider quality, cost, latency, adapter versions, and production delivery effects remain unmeasured. Independent review is still required.

## Pending work

Independent review, PR creation, and repository CI.

## Commit and pull request

Pending.
