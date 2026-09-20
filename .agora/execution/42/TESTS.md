---
issue: 42
tested_commit: working-tree
timestamp: 2026-09-20
---
# Tests: Reference architecture and shared responsibility

## Environment

Local Linux workspace; Python 3.11; current repository contracts and executable samples; no network services, cloud accounts, credentials, customer data, or provider SDKs used.

## Exact commands

`uv run pytest tests/test_commercial_architecture.py tests/test_commercial_packages.py -q`

Result: `9 passed in 0.02s`.

`uv run ruff check tests/test_commercial_architecture.py tests/test_commercial_packages.py`

Result: all checks passed.

`uv run ruff format --check tests/test_commercial_architecture.py tests/test_commercial_packages.py`

Result: two files already formatted.

`uv run python scripts/verify_all.py`

Result: all phases passed: lint; format (`302 files`); `526 passed, 2 skipped in 19.98s`; links; manifest; one Method Pack; eleven samples; package build/install and wheel-installed self-test.

## Cases executed

Required architecture sections and all three deployment patterns; technology-neutral primary Mermaid diagram with no cloud-vendor names; Core/flavor/Studio/runtime/tool boundaries; optional AWS, Azure, GCP, and on-premises mappings; replaceable components; at least eight failure/recovery paths; required identity, credential, isolation, residency, model-term, backup, and incident controls; explicit enforcement/validation/evidence/responsibility vocabulary; prohibited hosting, credential, compliance, Studio-write, and mandatory-cloud claims; cross-document links and every local link target.

## Result

All focused and full repository checks passed.

## Cases not executed

Independent architecture/security review, customer procurement review, cloud deployment, disaster-recovery exercise, legal/compliance assessment, or live external integration testing.

## Reason for omission

This issue produces vendor-neutral reference documentation. Those activities require independent reviewers, customer environments, accountable control owners, or separately scoped service work.

## Evidence

Exact command results above plus executable sample and security-policy links in the reference documents. Independent review and repository CI remain pending.
