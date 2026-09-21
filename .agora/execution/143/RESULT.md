---
issue: 143
status: partial
updated_at: 2026-09-21
pull_request: 144
---
# Result

## Summary
Added credential-free runtime discovery, doctor diagnostics and installer visibility for local AI CLIs.

## Security boundary
No credential files or tokens are read. Installation does not imply authentication. Detection never enables a runtime automatically.

## Remaining
Full CI and independent review.

## Pull request
PR #144.
