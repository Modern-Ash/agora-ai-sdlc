---
issue: 107
epic: 93
title: Add optional estimation, test-design and code-review enterprise rules
repository: Modern-Ash/agora-ai-sdlc
status: implementing
risk: medium
context_size: medium
budget:
  max_input_tokens: 32000
  max_output_tokens: 14000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Add optional estimation, test-design and code-review enterprise rules

## Objective
Add provider-neutral enterprise delivery controls for estimation, test design and code review while keeping them outside the canonical AWS-original method.

## Business outcome
Customers selecting the LG-enterprise compatibility target can enable explicit delivery controls without introducing story-point coupling, provider-specific review tooling or a second lifecycle authority.

## Allowed paths
- .agora/execution/107/**
- profiles/enterprise-controls/**
- src/agora_ai_sdlc/enterprise_controls.py
- src/agora_ai_sdlc/conformance/self_test.py
- tests/test_enterprise_controls.py
- docs/policies/enterprise-delivery-controls.md
- profiles/README.md

## Forbidden changes
- Agora Core
- Method Pack lifecycle/transitions/roles
- compatibility profile schema
- provider/model/cloud/SCM-specific integrations
- mandatory story points
- remote/network calls

## Functional requirements
- Versioned enterprise-control profile contract.
- AWS-original profile disables estimation, test-design and code-review controls.
- LG-enterprise enables test-design and code-review, and exposes estimation as optional/configurable.
- Neutral estimation metrics include effort range, elapsed time, AI cost and human review time.
- Test design declares required test classes and coverage obligations.
- Code review declares reviewer separation, required evidence and blocking finding severities.
- Conformance output labels every rule as an enterprise extension.
- These controls evaluate facts only; they never advance Core lifecycle state.

## Acceptance criteria
- [ ] Disabled by default in AWS-original.
- [ ] Configurable in LG-enterprise.
- [ ] Rules are provider-neutral.
- [ ] Conformance output distinguishes method requirement from enterprise extension.
- [ ] Unknown profile/config/evidence fails deterministically.
- [ ] Packaged self-test validates both profiles.
- [ ] Full repository verification passes.

## Focused verification
- uv run pytest -q tests/test_enterprise_controls.py
- uv run ruff check src/agora_ai_sdlc/enterprise_controls.py tests/test_enterprise_controls.py
- uv run ruff format --check src/agora_ai_sdlc/enterprise_controls.py tests/test_enterprise_controls.py

## Full verification
- uv run python scripts/verify_all.py

## Dependencies
#106 is merged to main. No Core change is required.

## Scope boundary
This issue defines and evaluates declarative delivery controls only. It does not estimate work with an LLM, execute tests, invoke code-review providers, or mutate lifecycle state.
