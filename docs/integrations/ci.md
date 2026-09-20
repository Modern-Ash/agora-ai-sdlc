# Generic CI/CD evidence profile

The `generic-ci-evidence` profile normalizes bounded observations from any CI/CD system. Agora Core
records and evaluates evidence; the external system remains responsible for executing builds,
tests, scans, deployments, and smoke tests. This profile never fetches logs or runs a pipeline.

## Evidence contract

Every observation uses `agora-ai-sdlc/ci-evidence/v1` and contains only:

- provider and immutable run identifier;
- canonical HTTPS repository URL and full 40- or 64-character commit id;
- environment;
- category and exact status;
- one to eight bounded HTTPS evidence references.

The seven categories are `build`, `unit`, `integration`, `security`, `quality`, `deployment`, and
`smoke-test`. Status is exactly one of `success`, `failure`, `cancelled`, or `unknown`; only
`success` can be positive. Unknown spellings are rejected rather than guessed.

References reject URL user information, query strings, fragments, non-HTTPS schemes, duplicates,
and values longer than 2,048 characters. The closed schema has no fields for logs, environment
dumps, tokens, response bodies, or arbitrary metadata. A reference proves where the bounded result
can be inspected; it does not copy provider output into Agora.

## Gate bundles

| Core evidence | Required current categories | Typical gate |
| --- | --- | --- |
| `test-suite` | build, unit, integration, quality | `build-verified` |
| `security-scan` | security | `completion` |
| `deployment` | deployment, smoke-test | `completion` |

Every required category must be successful and match the expected repository, commit, and
environment. A stale SHA, environment mismatch, failed, cancelled, or unknown result leaves the
bundle blocked. The Core evidence conversion records a blocked bundle as `failure`, never as
success. Core still owns gate evaluation and work revision state.

The identity `(provider, repository, run_id, category)` has a deterministic dedupe key. Repeating
the same normalized observation is a no-op. Reusing that identity with changed evidence is a
conflict and fails closed; corrections require a new external run identifier.

## Provider examples

The fixtures deliberately use all three shapes through the same normalized contract:

| Provider | Observation source | Canonical status mapping |
| --- | --- | --- |
| GitHub Actions | Core `github-actions/view-run` | completed + success -> `success`; other conclusions map explicitly |
| GitLab CI | Core `gitlab-ci/view-run` | success, failed, canceled, or unknown mapped explicitly |
| Jenkins | reviewed `ci-cd/view-run` wrapper | wrapper emits the neutral fields; Jenkins is not a privileged default |

No provider is canonical. An adapter translates provider output into the closed fact before this
profile evaluates it. Adapter execution errors remain provider failures; a valid fact that is stale
or non-successful is a policy denial.

## Usage

Run the offline multi-provider lifecycle:

```console
agora-ai-sdlc run-sample ci-evidence
```

For live use, call the reviewed Core adapter in read mode, normalize its bounded result, register
each evidence URL as an Agora artifact, and then add the resulting Core evidence input. Keep
credentials in the provider CLI/session. Do not persist CI variables, raw logs, or URLs containing
temporary query tokens.
