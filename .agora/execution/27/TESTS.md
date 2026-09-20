---
issue: 27
tested_commit: working-tree
timestamp: 2026-09-20
---
# Tests

## Environment
Python 3.13 through `uv`; Agora Core 0.8.2; offline fixtures; no GitHub credentials or provider calls.

## Exact commands
- `uv run ruff format src/agora_ai_sdlc/github_delivery.py tests/test_github_delivery.py tests/test_github_delivery_sample.py samples/github-delivery/run.py`
- `uv run ruff check src/agora_ai_sdlc/github_delivery.py tests/test_github_delivery.py tests/test_github_delivery_sample.py samples/github-delivery/run.py`
- `uv run pytest tests/test_github_delivery.py tests/test_github_delivery_sample.py -q`
- `uv run ruff format .`
- `uv run python scripts/verify_all.py`

## Cases executed
Core adapter contract matching; default read-only authorization; capability and confirmation requirements for every write/destructive operation; normalized success; stale SHA; mismatched branch/run; failed and pending checks; missing approval; malformed provider facts; idempotent ingest; Core permission denial; executable sample; full repository verification and wheel smoke.

## Result
Focused: 16 passed. Full: 293 passed, 2 skipped; links, manifest, Method Pack, two samples, and package phases passed.

## Cases not executed
Opt-in live GitHub read smoke; write operations against GitHub; independent external-agent review.

## Reason for omission
Default verification is credential-free. Live reads and writes require separately approved accounts/repositories. Exporting the diff to another agent session was not authorized; review remains pending in the pull request.

## Evidence
`scripts/verify_all.py` ended with `[verify] all phases passed`.
