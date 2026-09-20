---
issue: 28
tested_commit: working-tree
timestamp: 2026-09-20
---
# Tests

## Environment
Python 3.13 through `uv`; Agora Core 0.8.2; offline fixtures; no CI provider credentials or network calls.

## Exact commands
- `uv run ruff format src/agora_ai_sdlc/ci_evidence.py tests/test_ci_evidence.py tests/test_ci_evidence_sample.py samples/ci-evidence/run.py`
- `uv run ruff check src/agora_ai_sdlc/ci_evidence.py tests/test_ci_evidence.py tests/test_ci_evidence_sample.py samples/ci-evidence/run.py`
- `uv run pytest tests/test_ci_evidence.py tests/test_ci_evidence_sample.py -q`
- `uv run ruff check .`
- `uv run python scripts/verify_all.py`

## Cases executed
Core neutral contract and adapter compatibility; four-status matrix; stale commit; repository/environment mismatch; unsafe and excessive references; closed schema; idempotent duplicate; changed duplicate conflict; complete and missing gate bundles; cross-context fact rejection; invalid status/category/commit; Core evidence mapping; executable three-provider lifecycle sample.

## Result
Focused: 20 passed. Full: 313 passed, 2 skipped; links, manifest, Method Pack, three samples, and package phases passed.

## Cases not executed
Live GitHub Actions, GitLab CI, or Jenkins reads; pipeline writes; external-agent review.

## Reason for omission
Default verification is credential-free. Live provider checks require separately approved accounts and systems. Independent review remains requested in the pull request.

## Evidence
`scripts/verify_all.py` ended with `[verify] all phases passed`.
