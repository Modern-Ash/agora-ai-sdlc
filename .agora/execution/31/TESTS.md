---
issue: 31
status: passed
tested_at: 2026-09-20
tester: Codex
---
# Tests: Observability and operational evidence

## Focused

Command:

```bash
uv run pytest tests/test_operational_evidence.py tests/test_operational_evidence_sample.py -q
```

Result: `23 passed in 1.18s`.

Command:

```bash
uv run ruff check src/agora_ai_sdlc/operational_evidence.py tests/test_operational_evidence.py tests/test_operational_evidence_sample.py samples/operational-evidence/run.py
```

Result: all checks passed.

The executable sample also completed directly with five equivalent providers, readiness allowed, a `propose` control-band result, a governed Intent, and zero production mutations.

## Repository-wide

Command:

```bash
uv run python scripts/verify_all.py
```

Result: all phases passed.

- Lint and format: passed (`208 files already formatted`).
- Tests: `417 passed, 2 skipped in 10.22s`.
- Links and flavor manifest: passed.
- Method Packs: one installed and validated with Agora Core.
- Samples: seven executed successfully.
- Package: wheel built, installed outside the repository, and smoke-tested.

## Coverage notes

Tests cover installed neutral Tool Pack parity, absence of provider dependencies, five-provider metric parity, unit/window validation, stale/future/wrong-environment metrics, current release/revision/environment binding, deployment/smoke completeness, failed releases, bounded references, Core evidence mapping, context-bound deduplication, blocked control-band input, and a real Core severe finding that creates a draft Intent without a Tool Run.

No live monitoring system was queried. The issue requires deterministic fixture mappings; live collection needs a separately reviewed neutral wrapper and non-production authorization.
