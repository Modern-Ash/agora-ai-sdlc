---
issue: 96
reviewed_commit: main
reviewer: ChatGPT independent session
verdict: changes-requested
updated_at: 2026-09-21
---
# Independent review

## Verdict

Changes requested before closing #96.

## Scope reviewed

- `contracts/conformance/aws-original-rules-v1.yaml`
- `contracts/conformance/aws-original-rules-v1.schema.json`
- `src/agora_ai_sdlc/conformance/aws_original.py`
- `tests/conformance/test_aws_original_rules.py`
- `tests/fixtures/conformance/aws-original/**`
- `profiles/compatibility/aws-original/profile.yaml`
- `docs/reference/conformance.md`
- recorded CI evidence for PR #110 / promotion PR #111

## Findings

### Blocking — stable PASS/PARTIAL/FAIL fixture coverage was not durable

Issue #96 requires golden fixtures covering PASS, PARTIAL and FAIL. The implementation originally satisfied that through the mutable `current.yaml` repository snapshot. Subsequent fidelity work changed the repository so the current snapshot now contains PASS and PARTIAL but no FAIL.

That makes the acceptance criterion dependent on unrelated future repository evolution and removes a deterministic regression test for FAIL derivation.

Required remediation: add immutable fixture roots that independently exercise PASS, PARTIAL and FAIL for at least one representative rule through the real `derive_facts()` provider.

## Observations

- The rule provider is offline and path-confined.
- Base-method rules and Agora additive governance are correctly separated.
- Rule/profile coverage fails closed for missing or undeclared capabilities.
- Current repository fidelity has improved since the original #96 result; the historical RESULT/TESTS snapshot should not be read as the current conformance state.

## Re-review condition

Approve once stable PASS/PARTIAL/FAIL fixture roots are added and full CI passes.
