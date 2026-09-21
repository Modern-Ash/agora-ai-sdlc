---
issue: 95
epic: 91
title: Implement machine-readable conformance engine and CLI
repository: Modern-Ash/agora-ai-sdlc
base_commit: 52a4e5a7e46a75213c7fb3a2dd4aff1dc763b47c
status: implementing
risk: medium
context_size: medium
budget:
  max_input_tokens: 32000
  max_output_tokens: 14000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Implement machine-readable conformance engine and CLI

## Objective
Implement an offline, deterministic compatibility conformance engine and CLI over the versioned compatibility profiles introduced by #94.

## Business outcome
Provide the executable foundation for verifiable compatibility claims. The engine must turn profile requirements plus project/repository capability facts into a stable PASS/PARTIAL/FAIL/NOT_APPLICABLE report, suitable for humans, automation, CI and later Marketplace evidence generation.

## Current state
Compatibility profiles are versioned and validated, but there is no evaluator, facts contract, result contract or `agora-ai-sdlc conformance` command. Issue #96 will add AWS-original fidelity rules; this issue must remain generic and profile-driven.

## Required inputs
- GitHub issue #95 and parent epic #91.
- `AGENTS.md`.
- `src/agora_ai_sdlc/compatibility_profiles.py`.
- `src/agora_ai_sdlc/cli.py`.
- existing conformance contracts and tests.

## Allowed paths
- `.agora/execution/95/**`
- `src/agora_ai_sdlc/conformance/**`
- `src/agora_ai_sdlc/cli.py`
- `contracts/conformance/conformance-facts-v1.schema.json`
- `contracts/conformance/conformance-result-v1.schema.json`
- `tests/conformance/test_compatibility_engine.py`
- `tests/test_cli.py`
- `docs/reference/conformance.md`

## Forbidden changes
- Agora Core.
- compatibility-profile v1 contract or manifests from #94.
- Method Pack lifecycle/gates/roles.
- provider/vendor-specific API calls or SDKs.
- hard-coded AWS/LG scoring rules; those belong to later tickets.
- network access during evaluation.

## Functional requirements
- Define a versioned local capability-facts contract.
- Define a versioned conformance-result JSON schema.
- Load facts from an explicit file or the default project-local path.
- Evaluate every profile capability deterministically.
- Required capability with no fact => FAIL.
- Optional capability with no fact => NOT_APPLICABLE.
- Unsupported capability => NOT_APPLICABLE.
- Explicit facts may report PASS/PARTIAL/FAIL/NOT_APPLICABLE.
- Every emitted capability result includes evidence/reason, source contract version and remediation when not passing.
- Produce a deterministic overall status.
- Add `agora-ai-sdlc conformance <profile>` with human-readable output and `--json`.
- Add `--strict`: return non-zero only when the evaluated report contains FAIL.
- Unknown profile, invalid facts, or invalid input path return usage/data error code 2.

## Non-functional requirements
- Offline and credential-free.
- Stable error codes for facts/engine input errors.
- Stable result ordering independent of YAML map ordering.
- No new runtime dependency.
- No vendor-specific semantics in the engine.

## Acceptance criteria
- [ ] Deterministic evaluation from a compatibility profile and facts.
- [ ] PASS/PARTIAL/FAIL/NOT_APPLICABLE emitted per capability.
- [ ] Evidence/reason, profile contract version and remediation fields emitted.
- [ ] Human-readable CLI output supported.
- [ ] JSON CLI output supported and conforms to checked-in schema shape.
- [ ] Strict mode returns non-zero when any FAIL exists.
- [ ] Non-strict mode returns zero for a valid report even when it contains FAIL.
- [ ] Missing required facts fail closed.
- [ ] Optional missing facts become NOT_APPLICABLE.
- [ ] Invalid/unknown facts fail with stable errors.
- [ ] Evaluation performs no network access.
- [ ] Existing CLI commands and tests remain compatible.

## Negative cases
- facts file missing when explicitly requested;
- invalid facts schema;
- duplicate capability facts;
- unknown status;
- unknown capability fact not declared by selected profile;
- malformed evidence/remediation fields;
- unknown compatibility profile.

## Focused verification
- `uv run pytest -q tests/conformance/test_compatibility_engine.py tests/test_cli.py`
- `uv run ruff check src/agora_ai_sdlc/conformance src/agora_ai_sdlc/cli.py tests/conformance/test_compatibility_engine.py tests/test_cli.py`
- `uv run ruff format --check src/agora_ai_sdlc/conformance src/agora_ai_sdlc/cli.py tests/conformance/test_compatibility_engine.py tests/test_cli.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
#94 is merged and closed. #96/#97 consume this engine but are not prerequisites.

## Clarifications
None required. This ticket defines a generic evaluator; methodology-specific evidence derivation is intentionally deferred.

## Completion evidence
- Exact CI commands/results in `TESTS.md`.
- implementation summary in `RESULT.md`.
- independent review in `REVIEW.md` before merge.
