---
issue: 38
tested_commit: working-tree
timestamp: 2026-09-20
---
# Tests: Existing-codebase multi-LLM pilot

## Environment

Local Linux workspace; Python 3.11; Agora Core 0.8.2 contract range; default checks use only fake runners and local Git repositories.

## Exact commands

`uv run pytest tests/test_existing_codebase_pilot.py tests/conformance/runtimes/test_matrix.py -q`

Result: `8 passed in 1.67s`.

`uv run ruff check samples/existing-codebase-pilot/run.py samples/existing-codebase-pilot/fake_runner.py tests/test_existing_codebase_pilot.py`

Result: all checks passed.

`uv run ruff format --check samples/existing-codebase-pilot/run.py samples/existing-codebase-pilot/fake_runner.py tests/test_existing_codebase_pilot.py`

Result: three files already formatted.

`uv run agora-ai-sdlc run-sample existing-codebase-pilot`

Result: completed; Core validation ok; baseline/rejected/accepted commits recorded; provider replacement and unchanged Method Pack confirmed; first review and gate rejected; corrected review and CI bundle accepted.

`uv run python scripts/verify_all.py`

Result: all phases passed: lint; format (`279 files`); `511 passed, 2 skipped in 14.13s`; links; flavor manifest; one Method Pack; eleven executable samples; package smoke test.

`uv build --out-dir /tmp/agora-ai-sdlc-issue38-wheel --quiet && uv venv --clear --quiet /tmp/agora-ai-sdlc-issue38-wheel/venv && uv pip install --quiet --python /tmp/agora-ai-sdlc-issue38-wheel/venv/bin/python /tmp/agora-ai-sdlc-issue38-wheel/agora_ai_sdlc-*.whl && /tmp/agora-ai-sdlc-issue38-wheel/venv/bin/agora-ai-sdlc run-sample existing-codebase-pilot`

Result: installed-wheel pilot completed with Core validation ok and all expected rejection, correction, provenance, provider-replacement, CI, and metric fields.

## Cases executed

Baseline and result behavior; invalid quantities; provider replacement; Method Pack immutability; adapter-shaped Codex, Claude, and generic fake sessions; non-approving and approving independent review; distinct actor/provider policy; blocked Core gate; current-commit CI bundle; completion; cleanup; all existing runtime combinations; source and wheel packaging.

## Cases not executed

Live model/provider calls, external CI, production deployment, Python 3.12/3.13 locally, and credentialed GitHub delivery.

## Reason for omission

Live execution is optional and operator-controlled; default CI must remain credential-free and deterministic. The repository CI matrix is responsible for supported Python versions.

## Evidence

Command outputs above and the sample's machine-checkable JSON summary. Independent review remains pending.
