---
issue: 32
status: passed
tested_at: 2026-09-20
tester: Codex
---
# Tests: Starter profile and bootstrap

## Focused

`uv run pytest tests/test_starter.py tests/test_starter_sample.py -q`

Result: `13 passed in 1.04s`.

`uv run ruff check src/agora_ai_sdlc/starter.py src/agora_ai_sdlc/cli.py tests/test_starter.py tests/test_starter_sample.py samples/starter/run.py`

Result: all checks passed.

## Repository-wide

`uv run python scripts/verify_all.py`

Result: all phases passed: lint and format (`217 files`), `430 passed, 2 skipped in 11.03s`, links, flavor manifest, one Method Pack, eight executable samples, and wheel smoke test.

## Coverage

Tests cover the exact Method Pack pin, deterministic pure preview, cancellation before target/home creation, fresh and existing Git repositories, preservation of existing files, human-only execution, one-runtime execution, two-runtime limit, invalid profile/runtime/role references, explicit `--yes` CLI application, Core validation, and first work state.

No runtime or provider process was launched. Credentials, external CLI installation, Studio, and remote registry behavior are outside the Starter bootstrap.
