---
issue: 131
epic: 93
title: Add LG-enterprise derived conformance and end-to-end reference sample
status: implementing
risk: medium
created_at: 2026-09-21
---
# Task

## Objective
Make the public lg-enterprise profile executable and replace TARGET_ONLY Marketplace status with evidence-derived conformance.

## Boundaries
- No proprietary LG behavior.
- No AWS/LG/provider/model/cloud/SCM dependency.
- Generic conformance engine remains authoritative.
- Missing dedicated risk/issue management stays PARTIAL rather than being overstated.

## Verification
- uv run pytest -q tests/conformance/test_lg_enterprise_rules.py tests/test_marketplace_evidence.py
- uv run python scripts/check_marketplace_evidence.py
- uv run python scripts/verify_all.py
