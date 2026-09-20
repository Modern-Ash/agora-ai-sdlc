---
issue: 20
status: partial
pull_request: pending
---
# Result
4 depth profiles (data), resolver/assessor/recommender, `profile` CLI subcommand, docs.

## Decisions / deviations
- Baseline = pack gates = `standard`; `minimal` is the only profile that removes obligations (justified, protected intent approval).
- Only `standard` is enforced by Core; other depths are resolved and assessed only (advisory). This is the main gap vs the epic's intent.
- Where a work item's depth is stored is undefined.
- Regulated "signed actions / human final approval" are declared flags, not verified.
- Added `profile` subcommand to the CLI (issue only implied resolution); recommendation rules and the extras per depth are my proposal; confirm.
