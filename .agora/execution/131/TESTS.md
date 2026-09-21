---
issue: 131
status: passed
tested_commit: ca8e2828496d66f722d1a12e592bccc2f3f3437d
updated_at: 2026-09-21
---
# Tests

GitHub Actions run #181 passed on the final implementation head.

Run: https://github.com/Modern-Ash/agora-ai-sdlc/actions/runs/35642663931

## Verified
- lint
- format
- full pytest matrix
- links
- manifest
- Marketplace evidence drift
- Method Pack validation
- all bundled samples
- wheel build/install smoke test
- bundled self-test from installed wheel
- newest supported Agora Core compatibility

The lg-enterprise sample now passes both from source checkout and from the installed wheel.
