---
issue: 35
status: passed
tested_at: 2026-09-20
tester: Codex
---
# Tests: Modernization profile

## Focused

`uv run pytest tests/test_modernization.py tests/test_modernization_sample.py tests/test_templates.py -q`

Result: `61 passed, 1 skipped in 1.15s`.

`uv run ruff check src/agora_ai_sdlc/modernization.py src/agora_ai_sdlc/artifacts.py tests/test_modernization.py tests/test_modernization_sample.py tests/test_templates.py samples/modernization/run.py`

Result: all checks passed.

## Repository-wide

`uv run python scripts/verify_all.py`

Result: all phases passed: lint, format (`256 files`), `477 passed, 2 skipped in 12.92s`, links, flavor manifest, one Method Pack, ten executable samples, and wheel smoke test.

## Coverage

Tests cover every profile gate; known and unknown behavior; invented unknown baselines; independently deployable, planned, traced slices; slice behavior coverage; conversion/equivalence per slice; regression and unresolved behavior; accepted-difference evidence, explanation and Product Owner authority; required evidence types; binding evidence to the current artifact revision; stale artifact digests; rollback artifact/evidence; fail-before-transition state preservation; all new templates; and the complete credential-free scenario.

No legacy runtime, converter, provider, network service, credential, production deployment, backup restoration, or multi-repository operation was exercised.

