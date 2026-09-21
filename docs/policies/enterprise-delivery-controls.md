# Enterprise delivery controls

Issue #107 adds three provider-neutral controls that are deliberately outside the canonical AWS-original public method: estimation, test design and code review. They are flavor-level enterprise extensions and never advance Agora Core lifecycle state.

## Compatibility behavior

| Control | AWS-original | LG-enterprise |
|---|---|---|
| Estimation | disabled | optional, configurable |
| Test design | disabled | enabled |
| Code review | disabled | enabled |

The AWS-original profile therefore preserves base method fidelity. Selecting LG-enterprise activates enterprise delivery expectations without adding AWS, LG, model, cloud, SCM or agent-runtime dependencies.

## Estimation

Estimation is metric-based rather than story-point based. The v1 neutral vocabulary is effort range, elapsed time, AI cost and human review time. LG-enterprise exposes estimation as an optional control, so projects can enable measurement without making story points mandatory.

## Test design

The LG-enterprise profile requires unit, integration and acceptance test classes, plus evidence that changed behavior and critical paths are covered. The profile is declarative: Agora validates supplied evidence and does not prescribe a test framework.

## Code review

The LG-enterprise profile requires reviewer separation by distinct actor, review-summary and test-summary evidence, and no unresolved critical or high blocking findings. The vocabulary is provider-neutral and can be satisfied by any SCM/review implementation that emits equivalent evidence.

## Conformance reporting

The evaluator returns the schema agora-ai-sdlc/enterprise-controls-conformance/v1. Every control carries classification and requirement values of enterprise-extension plus PASS, FAIL or DISABLED status. This makes the distinction from canonical method requirements explicit and machine-readable.

Disabled controls do not block conformance. Enabled controls fail closed when required evidence is missing or a configured blocking finding remains.

## Boundary

The module consumes facts only. It does not call provider APIs, invoke models, calculate estimates, run tests, perform code review, record Core approvals, or mutate lifecycle state.
