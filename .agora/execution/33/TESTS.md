---
issue: 33
status: passed
tested_at: 2026-09-20
tester: Codex
---
# Tests: Enterprise signed registry profile

## Focused

`uv run pytest tests/test_enterprise.py tests/test_enterprise_sample.py -q`

Result: `16 passed in 0.92s`.

`uv run ruff check src/agora_ai_sdlc/enterprise.py tests/test_enterprise.py tests/test_enterprise_sample.py samples/enterprise/run.py`

Result: all checks passed.

## Repository-wide

`uv run python scripts/verify_all.py`

Result: all phases passed: lint, format (`228 files`), `446 passed, 2 skipped in 11.76s`, links, flavor manifest, one Method Pack, nine executable samples, and wheel smoke test.

## Coverage

Tests cover strict organization/project field separation; provider, budget, metric, and signature policy failures before writes; valid signature preview and install; untrusted, unmanaged, conflicting, invalid, and revoked trust paths; Core provenance and checksum fields; read-only upgrade preview; reviewed-checksum conflict; changed checksum for an installed version; failed archive verification without snapshot replacement; successful update history and recovery metadata; and exception records that cannot bypass policy.

The sample generates its Ed25519 private key only in process memory. No remote registry, credentials, network, provider runtime, Control Plane, or multi-project transaction was exercised.
