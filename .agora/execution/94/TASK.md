---
issue: 94
epic: 91
title: Define versioned AWS-original and LG-enterprise compatibility profiles
repository: Modern-Ash/agora-ai-sdlc
base_commit: 6b78b4103676017293649919107530232df1272f
status: implementing
risk: medium
context_size: medium
budget:
  max_input_tokens: 30000
  max_output_tokens: 12000
planner: ChatGPT
created_at: 2026-09-21
---
# Task: Define versioned AWS-original and LG-enterprise compatibility profiles

## Objective
Create versioned, machine-readable compatibility-profile contracts for the public AWS AI-DLC method definition and the public LG CNS enterprise AI-DLC presentation while preserving one provider-neutral Agora canonical model.

## Business outcome
Allow later conformance tooling and Marketplace evidence to evaluate compatibility without hard-coding AWS/LG concepts into Agora Core or binding customers to a cloud, model, SCM, or agent runtime.

## Current state
The repository documents AWS AI-DLC fidelity and contains adoption/depth/integration profiles, but it has no dedicated compatibility-profile schema, loader/validator, or AWS/LG compatibility manifests.

## Required inputs
- GitHub issue #94 and parent epic #91.
- `AGENTS.md`.
- `docs/reference/aws-ai-dlc-fidelity-plan.md`.
- Existing profile and conformance patterns under `profiles/`, `contracts/conformance/`, and `src/agora_ai_sdlc/conformance/`.

## Allowed paths
- `.agora/execution/94/**`
- `profiles/compatibility/**`
- `contracts/conformance/compatibility-profile-v1.schema.json`
- `src/agora_ai_sdlc/compatibility_profiles.py`
- `src/agora_ai_sdlc/conformance/self_test.py`
- `tests/test_compatibility_profiles.py`
- `tests/conformance/test_self_test.py`
- `docs/reference/compatibility-profiles.md`
- `profiles/README.md`

## Forbidden changes
- Agora Core repository or Core contracts.
- Existing Method Pack lifecycle, gates, roles, or behavior.
- Existing adoption/depth/integration profile semantics.
- Provider-specific runtime dependencies.
- Claims of AWS or LG affiliation, endorsement, certification, or access to non-public implementation details.

## Functional requirements
- Add schema `agora-ai-sdlc/compatibility-profile/v1`.
- Add versioned `aws-original` and `lg-enterprise` manifests.
- Map presentation stages to a small canonical Agora element vocabulary.
- Declare required, optional, and unsupported capability ids.
- Validate ids, versions, source scope, stage mappings, capability-set disjointness, and neutrality declarations.
- Fail deterministically for unknown canonical mappings and duplicate canonical mappings.
- Discover the new profiles in the packaged self-test without altering existing profile behavior.

## Non-functional requirements
- Offline/credential-free.
- Deterministic validation and stable error codes.
- No new third-party dependency.
- Provider/model/cloud/SCM neutrality is explicit in both manifests.
- Checked-in JSON schema documents the public contract.

## Acceptance criteria
- [ ] AWS-original and LG-enterprise manifests load and validate.
- [ ] Profiles conform to the checked-in schema contract.
- [ ] Unknown canonical stage mapping fails with a stable error code.
- [ ] Duplicate canonical stage mapping fails with a stable error code.
- [ ] Duplicate presentation stage ids fail deterministically.
- [ ] Capability categories are declared and pairwise disjoint.
- [ ] Existing profile loading/behavior remains unchanged.
- [ ] Packaged self-test discovers both compatibility profiles.
- [ ] Documentation explains canonical vs presentation semantics and non-affiliation/public-source scope.

## Negative cases
- Unknown schema/version.
- Unknown canonical element.
- Duplicate canonical mapping across stages.
- Duplicate stage id.
- Empty/invalid capability id.
- Capability appearing in more than one category.
- Neutrality dimension omitted or set false.
- Non-public source scope.

## Focused verification
- `uv run pytest -q tests/test_compatibility_profiles.py tests/conformance/test_self_test.py`
- `uv run ruff check src/agora_ai_sdlc/compatibility_profiles.py tests/test_compatibility_profiles.py`
- `uv run ruff format --check src/agora_ai_sdlc/compatibility_profiles.py tests/test_compatibility_profiles.py`

## Full verification
- `uv run python scripts/verify_all.py`

## Dependencies
None. Issue #94 is contract work and does not depend on later conformance-engine or Method Pack implementation tickets.

## Clarifications
None required. The issue defines a contract layer only; it does not change lifecycle behavior.

## Completion evidence
- Changed files and exact checks recorded in `TESTS.md` and `RESULT.md`.
- Independent review recorded in `REVIEW.md`.
- Pull request links #94 and does not self-merge.
