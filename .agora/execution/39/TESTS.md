---
issue: 39
tested_commit: working-tree
timestamp: 2026-09-20
---
# Tests: Single-command conformance harness

## Environment

Local Linux workspace; Python 3.11; Agora Core in the supported `>=0.8.2,<0.9` range; no network, LLM account, provider credential, or cloud service used by the harness.

## Exact commands

`uv run pytest tests/conformance/test_self_test.py tests/test_cli.py tests/test_verify_all.py -q`

Result: `10 passed in 3.73s` after anchoring sample repositories under the diagnostic workspace.

`uv run ruff check src/agora_ai_sdlc/conformance src/agora_ai_sdlc/cli.py tests/conformance/test_self_test.py tests/test_cli.py scripts/verify_all.py`

Result: all checks passed.

`uv run ruff format --check src/agora_ai_sdlc/conformance src/agora_ai_sdlc/cli.py tests/conformance/test_self_test.py tests/test_cli.py scripts/verify_all.py`

Result: six files already formatted.

`uv run agora-ai-sdlc self-test --json`

Result: exit 0; 13 checks passed; one Method Pack, fourteen profiles, four policies, twenty-five templates, five JSON contracts, and eleven samples discovered; human, AI, represented-swarm, and rejected-service paths exercised; workspace cleaned.

`uv run python scripts/verify_all.py`

Result: all phases passed: lint; format (`289 files`); `517 passed, 2 skipped in 19.44s`; links; manifest; one Method Pack; eleven samples; package build/install; wheel-installed self-test.

`uv run pytest tests/conformance/test_self_test.py -q`

Result after strengthening interruption timing and retained-workspace coverage: `4 passed in 5.92s`; Ruff and format checks passed.

## Cases executed

Asset discovery and manifest reconciliation; profile loaders; policy/template/contract parsing; all samples; full Core lifecycle; human and AI role holders; represented-swarm holders; unsupported service rejection; caller repository preservation; `AGORA_HOME` restoration; successful cleanup; retained failed workspace; injected failure; interruption after Core state creation; CLI JSON/stdout and progress/stderr separation; non-zero failure exit; installed-wheel execution.

## Cases not executed

Live providers, external CI/cloud services, real credentials, Python 3.12/3.13 locally, malformed third-party plugins, or operating-system termination that bypasses Python cleanup.

## Reason for omission

Default conformance is deliberately offline and provider-neutral. CI supplies the supported Python version matrix. Uncatchable process termination cannot guarantee in-process cleanup.

## Evidence

Exact command results above and the schema-versioned JSON summary. Independent review remains pending.
