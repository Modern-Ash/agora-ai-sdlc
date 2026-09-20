---
issue: 36
status: passed-local-contract
tested_at: 2026-09-20
tester: Codex
---
# Tests: AI-SDLC Studio projection contract

## Focused

`.venv/bin/pytest tests/test_studio_projection_contract.py tests/test_flavor_manifest.py -q`

Result: `30 passed in 0.12s`.

`.venv/bin/ruff check tests/test_studio_projection_contract.py scripts/verify_all.py`

Result: all checks passed; format check passed.

`python -m json.tool` was run for the schema and all three fixtures. Result: all JSON parsed successfully.

## Repository-wide

`uv run python scripts/verify_all.py`

Result: all phases passed: lint, format (`270 files`), `510 passed, 2 skipped in 13.29s`, links, flavor manifest, one Method Pack, ten executable samples, and wheel smoke test. The package phase installed the wheel in an isolated environment and asserted the Studio projection schema was present.

## Coverage

Local tests cover required section envelopes; explicit unavailable reasons; schema-reference integrity; open lifecycle identifiers; an unknown future state; additive top-level, lifecycle and presentation fields; current/terminal state consistency; structured session-linked provenance and fallback semantics; non-authoritative presentation; missing-section rejection; path, credential and private-key exclusion; and packaged asset discovery.

Backward/forward producer tests in Agora Core and consumer/Chromium tests in Agora Studio were not run because their implementations do not exist yet. They are required by Core #55 and Studio #10 before issue #36 can close. No live provider, browser, external account or cross-repository implementation was exercised.
