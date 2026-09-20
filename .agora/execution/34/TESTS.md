---
issue: 34
status: passed
tested_at: 2026-09-20
tester: Codex
---
# Tests: Regulated profile

## Focused

`.venv/bin/pytest tests/test_regulated.py tests/test_independent_review.py tests/test_provenance.py tests/test_flavor_manifest.py -q`

Result: `93 passed in 0.71s`.

`.venv/bin/ruff check src/agora_ai_sdlc/regulated.py tests/test_regulated.py`

Result: all checks passed; format check passed.

## Repository-wide

`uv run python scripts/verify_all.py`

Result: all phases passed: lint, format (`264 files`), `498 passed, 2 skipped in 13.17s`, links, flavor manifest, one Method Pack, ten executable samples, and wheel smoke test.

## Coverage

Tests cover profile composition; human and active Ed25519 assignment requirements; prohibited role combinations before mutation; Core rejection of direct and unsigned critical actions; valid signature audit fields; stale Core preconditions; complete observed runtime/model/fallback provenance; exception authority, expiry, maximum duration, non-waivable controls, credential rejection and exclusive creation; retention completeness, expiry, binding and exclusive creation; and symlink escape rejection before filesystem writes.

No production key-management system, external identity provider, runtime adapter, WORM archive, legal hold, data deletion, network boundary, provider service, regulatory framework, or certification audit was exercised.
