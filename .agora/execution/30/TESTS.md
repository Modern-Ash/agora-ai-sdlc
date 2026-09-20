---
issue: 30
status: passed
tested_at: 2026-09-20
tester: Codex
---
# Tests: GitLab and Jira follow-on profiles

## Focused

Command:

```bash
uv run pytest tests/test_follow_on_delivery.py tests/test_follow_on_delivery_samples.py -q
```

Result: `37 passed in 0.75s`.

Command:

```bash
uv run ruff check src/agora_ai_sdlc/follow_on_delivery.py tests/test_follow_on_delivery.py tests/test_follow_on_delivery_samples.py samples/gitlab-delivery/run.py samples/jira-work-items/run.py
```

Result: all checks passed.

## Repository-wide

Command:

```bash
uv run python scripts/verify_all.py
```

Result: all phases passed.

- Lint and format: passed.
- Tests: `394 passed, 2 skipped in 9.98s`.
- Links and flavor manifest: passed.
- Method Packs: one installed and validated with Agora Core.
- Samples: six executed successfully, including GitLab and Jira.
- Package: wheel built, installed outside the repository, and smoke-tested.

## Coverage notes

Tests cover installed Core operation parity, neutral capability reuse, absence of provider branches in the Method Pack, read-only defaults, explicit write grants and confirmation, unsupported operations, GitLab/Jira fixture parity, stale and failed pipelines, review blockers, exact bounded references, malicious keys/IDs/project paths, external failure distinction, idempotent retries, and source-revision conflicts.

No live GitLab or Jira account test was run. The issue requires deterministic fixture contract tests; optional live smoke tests require explicit non-production credentials and confirmation.
