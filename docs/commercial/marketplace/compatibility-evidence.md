<!-- GENERATED FILE: run uv run python scripts/check_marketplace_evidence.py --write -->
# Compatibility evidence matrix

This file is generated from checked-in compatibility contracts and executable conformance rules.
It is release evidence, not a certification, affiliation, partnership, or endorsement claim.

## Matrix

| Evidence dimension | AWS-original | LG-enterprise | Agora-open |
| --- | --- | --- | --- |
| Current result | **PARTIAL** (executable repository conformance) | **TARGET_ONLY** (public profile declaration; implementation conformance not yet evaluated) | **PASS** (additive governance only) |
| PASS | ai-initiated-planning, domain-design, forward-backward-traceability, human-validation, intent, level-1-plan, non-functional-requirements, operations-observability, persistent-context, quality-reviewer, recursive-planning, units | Not reported as PASS until a dedicated LG rule provider exists | fail-closed-gates, independent-review, model-provenance, provider-neutrality |
| PARTIAL | bolts, brownfield-semantic-elevation, deployment-units, logical-design, measurement-criteria, minimal-roles, operations-governed-remediation, risk-register, three-phase-lifecycle, user-stories | Not evaluated | — |
| FAIL | — | Not evaluated | — |
| NOT_APPLICABLE / optional | prfaq | effort-estimation | — |
| Required target capabilities | Derived by executable rules | change-configuration-management, code-review, cross-repository-impact, documentation, domain-knowledge, ideation, operational-rules, organizational-readiness, quality-governance, review-gates, risk-issue-management, security-compliance, technical-setup, test-design, traceability | Additive controls, not base-method requirements |
| Evidence | [contracts/conformance/aws-original-rules-v1.yaml](../../../contracts/conformance/aws-original-rules-v1.yaml), [tests/fixtures/conformance/aws-original/current.yaml](../../../tests/fixtures/conformance/aws-original/current.yaml), [tests/conformance/test_aws_original_rules.py](../../../tests/conformance/test_aws_original_rules.py) | [profiles/compatibility/lg-enterprise/profile.yaml](../../../profiles/compatibility/lg-enterprise/profile.yaml), [docs/reference/compatibility-profiles.md](../../../docs/reference/compatibility-profiles.md) | [contracts/conformance/aws-original-rules-v1.yaml](../../../contracts/conformance/aws-original-rules-v1.yaml), [tests/conformance/test_aws_original_rules.py](../../../tests/conformance/test_aws_original_rules.py) |
| Boundary | Public-method fidelity only; PARTIAL/FAIL remain visible | Public target semantics only; no private/proprietary implementation behavior is modeled | Agora-specific governance is never counted as AWS-original fidelity |

## Claim boundaries

- AWS-original statuses come from the repository-derived conformance provider and cannot be promoted by editing this document.
- LG-enterprise currently represents a public compatibility target only. TARGET_ONLY must not be rewritten as PASS, PARTIAL, or verified implementation compatibility.
- Agora-open reports additive governance such as fail-closed gates, independent review, provider neutrality, and model/session provenance; those controls do not upgrade AWS-original fidelity.
- Proprietary or non-public AWS/LG prompts, source code, scoring, implementation details, partner status, certification, sponsorship, or endorsement are not evaluated or claimed.
- Marketplace and release copy must preserve current PARTIAL/FAIL states and link back to this generated evidence.

## Regeneration

Run: uv run python scripts/check_marketplace_evidence.py --write

CI runs the checker without --write and fails when this file is missing or differs from regeneration.
