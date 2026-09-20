---
issue: 31
status: implemented
implemented_at: 2026-09-20
implementer: Codex
review: pending-independent
---
# Result: Observability and operational evidence

## Outcome

Added a provider-neutral operational-evidence profile that turns bounded metric, deployment, and smoke observations into current release readiness and deterministic Agora Core control-band evaluations.

## Delivered

- Neutral metric shape with exact unit/window contracts and five-minute freshness.
- Optional CloudWatch, Azure Monitor, GCP Monitoring, Prometheus, and OpenTelemetry fixture translators.
- Release, revision, environment, deployment, and smoke binding for Core `deployment` evidence.
- Reviewed `http.error_rate` control-band inputs backed by Agora Core 0.8.2.
- Credential-free sample proving lifecycle completion and a severe governed Intent without production mutation.
- Reference documentation covering authority, failure behavior, provider optionality, and unsupported incident writes.

## Acceptance evidence

- Provider names occur only in mappings, fixtures, and documentation; no provider package was added.
- Stale, future, wrong-environment, wrong-release/revision, failed, or incomplete observations cannot produce positive readiness.
- A real Core `propose` finding creates a draft Intent and no Tool Run.
- Missing unit or window raises a stable validation error.

## Limits

- Fixtures demonstrate translation contracts; no live provider or neutral wrapper is invoked.
- The profile exposes read-only metric and health operations. Incident creation/update/resolution remain outside scope.
- One reviewed metric is included. Additional metrics require explicit unit, window, and baseline review.
- Independent review remains pending.

## Verification

Focused checks: `23 passed`; Ruff passed. Full verification: `417 passed, 2 skipped`; all phases passed, including seven samples and wheel smoke test. Exact commands are recorded in `TESTS.md`.
