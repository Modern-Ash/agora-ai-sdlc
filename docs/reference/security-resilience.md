# Security and offline resilience verification

Issue #40 adds adversarial tests around the shipped conformance harness and existing Core boundaries. These tests run without provider credentials, accounts, cloud services, or network access and do not add a runtime, scanner, secret store, or recovery engine.

## Canary and secret boundary

The security suite places the inert value `agora-canary-secret-40-do-not-persist` in an environment variable, runs the complete packaged self-test, retains its otherwise temporary workspace, and scans its result, progress messages, and every generated file. Any occurrence fails the suite. Representative provenance and CI-reference inputs also attempt to carry the canary through forbidden credential fields and URL query data; validation must reject them without echoing the value.

This proves that repository-owned default conformance paths do not copy an unrelated inherited environment value. It is not a general secret scanner or DLP guarantee. Agora Core stores bounded runner stdout/stderr as durable diagnostics. Runtime wrappers and integration adapters must redact at the source and must not emit credentials, prompts containing sensitive data, raw reports, or authorization material. Customer secret injection, process isolation, log controls, and incident response remain deployment responsibilities.

The canary deliberately does not resemble a real provider credential. Real tokens and private keys never belong in fixtures, logs, repository history, or test output.

## Network-disabled suite

The complete `agora-ai-sdlc self-test` runs while Python socket connection entry points raise immediately. It discovers every shipped profile and sample, exercises real Core lifecycle state, and runs all eleven credential-free samples. A new default path that attempts a network connection fails the test instead of depending on DNS, a local service, or an external account.

Subprocesses remain limited to repository-owned fake runners and local Git/Core commands. The network guard is a deterministic application-level test, not an operating-system firewall or proof that arbitrary third-party binaries cannot make network calls.

## Runtime failure matrix

| Failure | Observed contract | Routing behavior |
| --- | --- | --- |
| Malformed provider output | Core session may complete, but provider-specific normalization raises a parse/shape error | Treated as ordinary failure; no provider change |
| Timeout | Core records failed session, exit code `124`, `termination_reason=timeout`, bounded diagnostics, and resume guidance | Ordinary failure; no provider change |
| Quota | Caller supplies Core's structured `quota` signal rather than parsing provider log text | May select only the next configured, eligible, explicitly authorized fallback |
| Cancelled CI run | Neutral CI fact records `status=cancelled` and blocker `ci.status.cancelled` | Does not satisfy evidence and does not trigger runtime fallback |
| Runner unavailable | Core rejects the missing executable before creating a session | Structured `runtime-unavailable` may select only an authorized eligible fallback |

The matrix keeps categories distinguishable even where policy gives several categories the same fail-closed result. Timeouts, malformed output, cancellation, output limits, and ordinary nonzero exits never masquerade as quota. Runtime selection still rechecks data, review, and budget policy for every fallback candidate.

## Registry failure injection

The resilience suite injects failures at four boundaries: install preview, install apply, upgrade preview, and upgrade apply. Preview failures must write nothing. Apply failures must leave no partial replacement; an install may leave an already validated public trust-key record, but no registry snapshot, and the Core project must remain valid. Upgrade failures preserve the exact previously installed version and checksum and leave the project valid.

These tests exercise failure before Core returns from an operation. Core's registry installation/update implementation supplies transactional snapshot placement and backup restoration. Process or machine loss beyond the tested boundary still requires inspection of project state, `SOURCE.md`/`UPDATE.md`, and the configured registry before retry. Content rollback remains a reviewed signed forward release, never manual mutation of generated state.

## Run

```console
uv run pytest tests/security tests/resilience -q
uv run python scripts/verify_all.py
```

The full command remains the release gate and also runs the network-disabled/canary tests as part of the default pytest phase.
