---
issue: 96
epic: 91
title: Build AWS AI-DLC fidelity conformance rules
repository: Modern-Ash/agora-ai-sdlc
base_commit: c95afba520b3a4d56dca110338a3e8487ca375ba
status: implementing
risk: medium
context_size: medium
budget:
  max_input_tokens: 36000
  max_output_tokens: 16000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Build AWS AI-DLC fidelity conformance rules

## Objective
Encode the public AWS-original method definition into deterministic, offline conformance rules that derive capability facts from Agora AI-SDLC repository assets and feed the generic engine from #95.

## Business outcome
Turn the generic conformance engine into evidence-backed AWS-original fidelity evaluation. The report must show what Agora already implements, what is partial and what is still missing, without relying on vendor APIs or manually asserted scores.

## Current state
The aws-original compatibility profile exists. The generic conformance engine and CLI are implemented in the stacked dependency branch for #95. Current Method Pack 0.1.0 still differs from the published target in several areas documented by the fidelity plan.

## Required inputs
- Issue #96 and parent epic #91.
- #95 stacked branch and its conformance engine.
- `profiles/compatibility/aws-original/profile.yaml`.
- `docs/reference/aws-ai-dlc-mapping.md`.
- `docs/reference/aws-ai-dlc-fidelity-plan.md`.
- Current Method Pack, templates, artifact traceability, modernization and observability assets.

## Allowed paths
- `.agora/execution/96/**`
- `profiles/compatibility/aws-original/profile.yaml`
- `profiles/compatibility/aws-original/rules.yaml`
- `contracts/conformance/aws-original-rules-v1.schema.json`
- `src/agora_ai_sdlc/conformance/aws_original.py`
- `src/agora_ai_sdlc/conformance/__init__.py`
- `src/agora_ai_sdlc/cli.py`
- `tests/conformance/test_aws_original_rules.py`
- `tests/fixtures/conformance/aws-original/**`
- `tests/test_cli.py`
- `docs/reference/aws-ai-dlc-mapping.md`
- `docs/reference/conformance.md`

## Forbidden changes
- Agora Core.
- LG compatibility profile.
- Method Pack lifecycle/gates/roles implementation.
- proprietary or non-public AWS/LG prompts/behavior.
- network/provider/model/cloud dependencies.
- hard-coded final marketing claims that are not derived from rules/evidence.

## Functional requirements
- Define a versioned AWS-original rules contract.
- Every required aws-original capability has a rule and explicit Agora evidence targets.
- Add explicit rules for three-phase lifecycle, minimal roles and governed operational remediation.
- Classify rules as base-method fidelity or additive Agora governance.
- Derive PASS/PARTIAL/FAIL facts from files/content only.
- Emit evidence references and concrete remediation.
- Support fixture roots so pass/partial/fail behavior is testable.
- Add explicit CLI derivation mode: `agora-ai-sdlc conformance aws-original --derive`.
- Derived facts flow through the generic #95 evaluator rather than bypassing it.
- Keep rule evaluation offline/deterministic.

## Non-functional requirements
- Stable rule schema and error codes.
- Deterministic rule/result ordering.
- Rules are data-driven; Python interpreter supports a small closed check vocabulary.
- No hidden filesystem discovery outside the supplied project/repository root.
- Additive governance rules are reported separately by the provider API and are not scored as AWS base-method requirements.

## Acceptance criteria
- [ ] 3 canonical phases are checked.
- [ ] Intent, Unit and Bolt semantics are checked.
- [ ] Level 1 Plan and recursive decomposition are checked.
- [ ] Human approval before execution is checked.
- [ ] User stories, NFRs, risk register, measurement criteria and optional PRFAQ are checked.
- [ ] Domain Design, Logical Design and Deployment Units are checked.
- [ ] Persistent context memory and forward/backward traceability are checked.
- [ ] Minimal required roles with optional participants are checked.
- [ ] Brown-field semantic elevation is checked.
- [ ] Operations telemetry and human-approved remediation are checked.
- [ ] Every rule maps to explicit Agora files/capabilities.
- [ ] Base fidelity is separated from additive Agora governance.
- [ ] Golden pass/partial/fail fixtures exist.
- [ ] --derive produces a valid generic conformance report.
- [ ] No network access is required.

## Negative cases
- missing/invalid rules file;
- unknown rule/check type;
- rule for undeclared capability;
- required profile capability without a rule;
- duplicate rule capability;
- malformed evidence targets;
- additive governance entry accidentally scored as base fidelity.

## Focused verification
- `uv run pytest -q tests/conformance/test_aws_original_rules.py tests/test_cli.py`
- `uv run ruff check src/agora_ai_sdlc/conformance/aws_original.py src/agora_ai_sdlc/cli.py tests/conformance/test_aws_original_rules.py tests/test_cli.py`
- `uv run ruff format --check src/agora_ai_sdlc/conformance/aws_original.py src/agora_ai_sdlc/cli.py tests/conformance/test_aws_original_rules.py tests/test_cli.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
Stacked on #95 / PR #109. Do not merge #96 before #95.

## Clarifications
None required. The existing AWS mapping/fidelity plan is the project decision source; the public method remains an external compatibility target, not a dependency or endorsement.

## Completion evidence
- Exact CI commands/results in `TESTS.md`.
- implementation summary in `RESULT.md`.
- independent review in `REVIEW.md` before merge.
