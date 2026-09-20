---
issue: 21
status: complete
pull_request: pending
---
# Result
`samples/new-product/run.py`, `agora-ai-sdlc run-sample`, `agora_ai_sdlc.scenario` (Core driver moved from tests/support, reused by tests), verify_all discovers samples automatically and re-runs the sample from the built wheel.

## Notes
- Actors: human PO/QA, AI architect/builder/operator (simulated; no runtime involved).
- Covers one rework edge (construction -> inception); the other two edges are covered by tests/test_lifecycle.py, not by the sample.
- Completes the executable-sample part left open in #13/#15/#16 (partially; live delegated-execution checks for #15 are still not done).
