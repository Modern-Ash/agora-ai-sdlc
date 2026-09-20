---
issue: 29
tested_commit: working-tree
timestamp: 2026-09-20
---
# Tests

## Environment
Python 3.13 through `uv`; Agora Core 0.8.2; offline fixtures; no scanner credentials, raw reports, or network calls.

## Exact commands
- `uv run ruff format src/agora_ai_sdlc/security_findings.py tests/test_security_findings.py tests/test_security_findings_sample.py samples/security-findings/run.py`
- `uv run ruff check src/agora_ai_sdlc/security_findings.py tests/test_security_findings.py tests/test_security_findings_sample.py samples/security-findings/run.py`
- `uv run pytest tests/test_security_findings.py tests/test_security_findings_sample.py -q`
- `uv run ruff check .`
- `uv run python scripts/verify_all.py`

## Cases executed
Core security contract; complete depth/severity threshold matrix; unknown severity; scanner-name invariance; immutable original finding; resolution/accepted-risk/false-positive Core mapping; waiver role and human authority; incomplete decisions; unsafe report/decision references; raw body rejection; mutation detection; duplicate ids and order independence; success/failure Core evidence; executable lifecycle sample.

## Result
Focused: 44 passed. Full: 357 passed, 2 skipped; links, manifest, Method Pack, four samples, and package phases passed.

## Cases not executed
Live scanner reads; raw-report import; scanner writes; external-agent review.

## Reason for omission
Default verification is credential-free and stores only bounded references. Live systems and imports require separately approved credentials/data handling. Independent review remains requested in the pull request.

## Evidence
`scripts/verify_all.py` ended with `[verify] all phases passed`.
