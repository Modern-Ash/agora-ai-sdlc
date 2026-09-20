---
issue: 40
status: implemented
commit: pending
pull_request: pending
updated_at: 2026-09-20
---
# Result: Security, secret-leak and offline resilience tests

## Status

Implementation and verification complete; independent security review pending.

## Concise summary

Added offline/canary security verification, a five-category runtime failure matrix, and four-point Enterprise registry failure injection over existing flavor and Core contracts without adding provider dependencies or product behavior.

## Files modified

Three focused security/resilience test modules, a reference guide, testing and README links, and issue execution records.

## Decisions made

- Resolved issue #40's “#37 conformance” dependency by objective and owning paths to implemented #39; Studio is not involved.
- Used one inert text canary rather than a real provider credential pattern.
- Preserved Core's structured timeout and unavailable-runner behavior and flavor policy's explicit quota/runtime-unavailable signals instead of parsing provider text.
- Treated malformed output, timeout, and cancelled CI as distinguishable ordinary failures that cannot silently change provider.
- Injected failures around public Enterprise/Core boundaries and asserted valid state rather than duplicating Core transaction internals.
- Documented that arbitrary third-party stdout/stderr must be redacted before Core persists bounded diagnostics.

## Criteria satisfied

- Repository-owned default conformance does not copy the inherited canary into result, progress, or generated state.
- Representative credential fields and unsafe references reject without echoing the canary.
- All eleven packaged samples and validation complete while socket connection entry points are denied.
- Malformed output, timeout, quota, cancelled CI, and unavailable runner have distinct observable outcomes.
- Only quota and runtime-unavailable select fallback, and only through explicit authorized policy signals.
- Install/upgrade preview and apply failures leave no partial registry replacement; prior project state remains valid.

## Tests run

Focused security/resilience tests, Ruff lint/format checks, and full repository verification.

## Results

Focused: `11 passed`. Full: `544 passed, 2 skipped`; all phases passed, including eleven samples and installed-wheel self-test.

## Deviations

No OS-level network namespace was used. The deterministic socket guard protects repository-owned in-process conformance, and documentation explicitly avoids claiming firewall-level isolation. No Core internal code was changed.

## Remaining risks

An arbitrary runtime can emit sensitive content before Agora sees it, and Core preserves bounded diagnostics. External adapters/runtimes must redact at source. Abrupt process or machine loss beyond public operation boundaries may require manual inspection before retry. Independent security review and the CI Python matrix remain pending.

## Pending work

Independent review, PR creation, and repository CI. Live-provider resilience remains an explicitly authorized external smoke activity.

## Commit and pull request

Pending.
