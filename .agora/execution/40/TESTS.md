---
issue: 40
tested_commit: working-tree
timestamp: 2026-09-20
---
# Tests: Security, secret-leak and offline resilience

## Environment

Local Linux workspace; Python 3.11; installed editable Agora Core boundary; inert non-provider canary; no network service, LLM account, cloud account, provider credential, or live runtime used.

## Exact commands

`uv run pytest tests/security tests/resilience -q`

Initial result: `10 passed, 1 failed`; provenance rejected the forbidden `api_key` as `provenance.unknown_field` before secret-value classification. The assertion was corrected to accept either fail-closed rejection code while retaining the no-echo requirement.

Final result: `11 passed in 4.50s`.

`uv run ruff check tests/security tests/resilience`

Result: all checks passed.

`uv run ruff format --check tests/security tests/resilience`

Result: three files already formatted after applying Ruff formatting to two files.

`uv run python scripts/verify_all.py`

Result: all phases passed: lint; format (`318 files`); `544 passed, 2 skipped in 23.18s`; links; manifest; one Method Pack; eleven samples; package build/install and wheel-installed self-test.

## Cases executed

Complete packaged self-test with Python socket connections denied; eleven samples and Core validation; environment-canary scan over structured result, progress, and every retained generated file; secret-bearing provenance field and CI URL query rejection without value echo; malformed generic-provider output; real Core session timeout with exit code 124 and durable termination reason; explicit quota fallback; cancelled neutral CI evidence; missing runner rejection before session write; ordinary-failure no-fallback policy; install preview/apply and upgrade preview/apply injected failures; no partial registry replacement; prior file contents, registry version/checksum, and project validity after failure.

## Result

All focused and full repository checks passed.

## Cases not executed

Live providers, external services, real credentials, OS firewall/network namespace isolation, abrupt machine/process loss, Core internal post-commit crash injection, or Python 3.12/3.13 locally.

## Reason for omission

The default suite must remain offline and credential-free. The application-level socket guard covers repository-owned in-process paths, while CI supplies the supported Python matrix. Uncatchable termination and Core internal transaction tests belong to the owning Core repository; customer infrastructure isolation remains an external responsibility.

## Evidence

Exact command results above, retained-workspace canary scan, Core session records, normalized blocker/fallback assertions, and byte-level pre-failure project snapshots. Independent security review remains pending.
