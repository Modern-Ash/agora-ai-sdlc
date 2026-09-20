---
issue: 40
epic: 7
title: Add security, secret-leak and offline resilience tests
repository: Modern-Ash/agora-ai-sdlc
base_commit: ec21272
status: review
risk: high
context_size: large
planner: Codex
created_at: 2026-09-20
---
# Task: Security, secret-leak and offline resilience tests

## Objective

Add deterministic adversarial verification for secret rejection, offline operation, runtime/provider failure categories, and installation/update recovery without contacting external services or weakening Agora Core authority.

## Allowed paths

- `.agora/execution/40/`
- `tests/security/`
- `tests/resilience/`
- `tests/test_enterprise.py`
- `docs/reference/security-resilience.md`
- `docs/development/testing.md`
- `README.md`

## Forbidden changes

- Agora Core lifecycle, session, registry, or transaction implementation
- Flavor Method Packs, profiles, policies, samples, manifests, or integration semantics
- Real credential formats or values, network services, provider SDKs, cloud accounts, or live runners
- Claims that Agora can redact arbitrary external runner output after it has been emitted

## Functional requirements

- Scan generated self-test state and progress for an inert environment canary.
- Verify representative flavor validation rejects secret-bearing fields/references without echoing the canary.
- Run every packaged sample and validation path with socket connections denied.
- Exercise malformed provider output, real Core timeout, quota, cancelled CI run, and unavailable runner paths.
- Verify failure categories remain distinct and only explicitly allowed quota/runtime-unavailable signals can select fallback.
- Inject failures before and during Enterprise install/upgrade application and verify no partial registry replaces prior valid state.

## Acceptance criteria

- [x] Canary values are absent from generated durable records and progress; representative secret-bearing inputs are rejected without echo.
- [x] Malformed output, timeout, quota, cancellation, and unavailable runner remain distinguishable.
- [x] Default offline conformance completes with socket connections denied.
- [x] Installation/update failure leaves no partial replacement and preserves a valid prior project state.

## Negative cases

- A socket connection attempt fails the offline suite immediately.
- Secret echo in an exception, self-test result, progress message, or generated file fails the canary scan.
- Timeout/malformed/cancelled paths selecting provider fallback fail the runtime matrix.
- Partial registry placement or mutation of the prior installed snapshot fails recovery tests.

## Focused verification

- `uv run pytest tests/security tests/resilience -q`
- `uv run ruff check tests/security tests/resilience`

## Full verification

- `uv run python scripts/verify_all.py`

## Dependencies

- #24 data-handling policy is implemented.
- #39 single-command conformance harness is implemented and packaged.
- Issue #40 names “#37 conformance”; #37 is actually the Studio dashboard. The implemented conformance dependency by objective and owning paths is #39, while these tests require no Studio behavior.

## Clarifications

This task verifies the installed Core boundary rather than duplicating it. Core persists bounded runner diagnostics; callers and adapters must prevent secrets from reaching runner output. The canary suite proves repository-owned defaults do not leak inherited environment values, not that arbitrary third-party output is automatically redacted.

## Completion evidence

Implementation and verification in progress; independent security review pending.
