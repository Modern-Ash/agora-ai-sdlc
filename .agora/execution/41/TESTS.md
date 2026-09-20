---
issue: 41
tested_commit: working-tree
timestamp: 2026-09-20
---
# Tests: Professional Services packages

## Environment

Local Linux workspace; Python 3.11; current source flavor manifest; no network, marketplace, customer data, credentials, or external service used.

## Exact commands

`uv run pytest tests/test_commercial_packages.py -q`

Result: `4 passed in 0.03s`.

`uv run ruff check tests/test_commercial_packages.py`

Result: all checks passed.

`uv run ruff format --check tests/test_commercial_packages.py`

Result: one file already formatted.

`uv run python scripts/verify_all.py`

Result: all phases passed: lint; format (`296 files`); `521 passed, 2 skipped in 20.12s`; links; manifest; one Method Pack; eleven samples; package build/install; wheel-installed conformance self-test.

## Cases executed

Exact package inventory; front-matter shape; Method Pack, profile, and policy claims against the current flavor manifest; required problem/prerequisite/activity/deliverable/responsibility/metric/planning/exclusion/acceptance sections; both responsibility parties; implemented-versus-consulting label on every deliverable; goal and schedule disclaimers; common license/services boundary; prohibited guarantee, endorsement, certification, compliance, and price phrases; all local links.

## Cases not executed

Legal review, customer procurement review, pricing, marketplace submission, live service delivery, customer acceptance, or external marketing publication.

## Reason for omission

Those are human/business actions outside this repository implementation and require accountable review before use.

## Evidence

Exact command results above and machine-checked traceability to `src/agora_ai_sdlc/flavor/flavor.yaml`. Independent review remains pending.
