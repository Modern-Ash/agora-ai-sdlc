# Observability and operational evidence

The operational-evidence profile translates bounded monitoring observations into one provider-neutral contract and maps reviewed values to Agora Core control bands. Monitoring systems remain authoritative for telemetry and deployment facts; Agora remains authoritative for lifecycle state, evidence, and governed follow-up work.

## Neutral observations

A metric observation contains `name`, numeric `value`, `unit`, `window`, `environment`, HTTPS `source`, and timezone-aware `timestamp`. The profile currently reviews `http.error_rate` as `percent` over `5m`. Missing unit/window, unsupported metrics, non-finite values, unsafe references, timestamps outside the five-minute freshness limit, and wrong-environment facts fail closed.

Deployment and smoke observations additionally identify a release and full source revision. Both must be successful, fresh, and match the requested release, revision, and environment before the bundle maps to Core `deployment` evidence. A monitoring fact never changes an Agora lifecycle state directly.

## Optional provider mappings

Credential-free fixtures demonstrate equivalent translations from CloudWatch, Azure Monitor, GCP Monitoring, Prometheus, and OpenTelemetry field shapes. They are examples at the translation boundary, not runtime dependencies or bundled provider adapters. Live collection should use a separately reviewed wrapper implementing Core's neutral `observability/query-metrics` or `service-health` operation.

The profile stores only normalized fields, fingerprints, and bounded references. It does not retain raw responses, logs, credentials, query strings, or URL fragments.

## Control bands

The reviewed profile supplies the inputs for Core's deterministic control-band API. Core classifies a value as `normal`, `diagnose`, or `propose`. A `propose` finding creates a draft Intent whose diagnosis and remediation must pass normal Agora gates. Neither the profile nor Core's evaluation executes deployment, rollback, incident, or production mutation operations.

The installed neutral observability Tool Pack also declares incident writes. This read-only profile intentionally exposes only metric query and service-health reads; incident creation, update, and resolution are outside this profile.

## Prerequisites, permissions and failure modes

**Prerequisites.** A monitoring system reachable through a separately reviewed wrapper implementing Core's `observability/query-metrics` or `service-health` operation, and Agora Core 0.8.2 or later. The offline sample needs no monitoring account.

**Permissions.** Read-only: only metric query and service-health reads are exposed. Incident creation, update and resolution, deployment, rollback and other production mutations are outside this profile, and monitoring facts never change lifecycle state directly.

**Failure modes.**

| Situation | Result |
| --- | --- |
| Missing unit or window, unsupported metric, non-finite value, unsafe reference | Fail closed |
| Observation older than five minutes or from another environment | Fail closed |
| Deployment or smoke fact that is unsuccessful, stale, or for another release, revision or environment | No `deployment` evidence |
| Value in the `propose` band | Draft Intent that must still pass normal gates |

## Sample

```bash
uv run agora-ai-sdlc run-sample operational-evidence
```

The sample runs entirely in a temporary Git repository, normalizes all five fixture shapes, records current deployment evidence, evaluates a severe control-band value, confirms the governed Intent, and completes `agora validate` without network access.
