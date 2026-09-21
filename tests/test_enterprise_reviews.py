import pytest

from agora_ai_sdlc.enterprise_reviews import (
    EnterpriseReviewError,
    ReviewFact,
    available_policies,
    evaluate,
    load_policy,
)


def fact(review_id, roles, evidence, independent=()):
    return ReviewFact(review_id, tuple(roles), tuple(evidence), tuple(independent))


def test_packaged_review_policies_validate():
    assert available_policies() == ("enterprise", "regulated", "starter")
    starter = load_policy("starter")
    enterprise = load_policy("enterprise")
    regulated = load_policy("regulated")

    assert starter.review("architecture-review").mandatory is False
    assert starter.review("security-compliance-review").mandatory is False
    assert all(review.mandatory for review in enterprise.reviews)
    assert all(review.mandatory for review in regulated.reviews)
    assert regulated.review("security-compliance-review").independent_review_profiles == ("regulated",)


def test_starter_allows_non_critical_reviews_to_be_optional():
    policy = load_policy("starter")
    result = evaluate(
        policy,
        (
            fact("business-review", ["product-owner"], ["business-decision"]),
            fact("quality-review", ["quality-reviewer"], ["quality-review"], ["distinct-actor"]),
            fact("operational-readiness-review", ["operator"], ["operational-readiness"]),
        ),
    )

    assert result.allowed
    by_id = {review.id: review for review in result.reviews}
    assert by_id["architecture-review"].status == "OPTIONAL_MISSING"
    assert by_id["security-compliance-review"].status == "OPTIONAL_MISSING"
    assert by_id["business-review"].status == "PASS"


def test_enterprise_requires_all_five_reviews():
    policy = load_policy("enterprise")
    result = evaluate(
        policy,
        (
            fact("business-review", ["product-owner"], ["business-decision"]),
            fact("architecture-review", ["architect"], ["architecture-review", "approved-impact-analysis"], ["distinct-actor"]),
            fact(
                "security-compliance-review",
                ["security-reviewer"],
                ["security-review", "compliance-review"],
                ["distinct-actor"],
            ),
            fact(
                "quality-review",
                ["quality-reviewer"],
                ["quality-review", "test-summary"],
                ["distinct-actor", "human-final"],
            ),
            fact(
                "operational-readiness-review",
                ["operator"],
                ["operational-readiness", "rollback-evidence"],
                ["distinct-actor"],
            ),
        ),
    )

    assert result.allowed
    assert {review.status for review in result.reviews} == {"PASS"}


def test_missing_mandatory_review_blocks_progress():
    result = evaluate(load_policy("enterprise"), ())

    assert not result.allowed
    assert all(review.status == "BLOCKED" for review in result.reviews)
    assert {blocker["code"] for review in result.reviews for blocker in review.blockers} == {
        "enterprise-review.missing"
    }


def test_missing_mandatory_approval_or_evidence_blocks():
    policy = load_policy("enterprise")
    result = evaluate(
        policy,
        (
            fact("business-review", [], ["business-decision"]),
            fact("architecture-review", ["architect"], [], ["distinct-actor"]),
            fact(
                "security-compliance-review",
                ["security-reviewer"],
                ["security-review", "compliance-review"],
                ["distinct-actor"],
            ),
            fact(
                "quality-review",
                ["quality-reviewer"],
                ["quality-review", "test-summary"],
                ["distinct-actor", "human-final"],
            ),
            fact(
                "operational-readiness-review",
                ["operator"],
                ["operational-readiness", "rollback-evidence"],
                ["distinct-actor"],
            ),
        ),
    )

    assert not result.allowed
    codes = {blocker["code"] for review in result.reviews for blocker in review.blockers}
    assert "enterprise-review.approval" in codes
    assert "enterprise-review.evidence" in codes


def test_independent_review_requirement_is_enforced():
    policy = load_policy("enterprise")
    requirement = policy.review("quality-review")

    result = evaluate(
        policy,
        (
            fact("business-review", ["product-owner"], ["business-decision"]),
            fact("architecture-review", ["architect"], ["architecture-review", "approved-impact-analysis"], ["distinct-actor"]),
            fact(
                "security-compliance-review",
                ["security-reviewer"],
                ["security-review", "compliance-review"],
                ["distinct-actor"],
            ),
            fact(
                "quality-review",
                requirement.required_approval_roles,
                requirement.required_evidence_types,
                ["distinct-actor"],
            ),
            fact(
                "operational-readiness-review",
                ["operator"],
                ["operational-readiness", "rollback-evidence"],
                ["distinct-actor"],
            ),
        ),
    )

    assert not result.allowed
    quality = next(review for review in result.reviews if review.id == "quality-review")
    assert quality.status == "BLOCKED"
    assert quality.blockers == (
        {
            "code": "enterprise-review.independent",
            "message": "missing independent-review decisions: human-final",
        },
    )


def test_regulated_requires_governance_and_regulated_review_decisions():
    policy = load_policy("regulated")
    facts = []
    for requirement in policy.reviews:
        facts.append(
            fact(
                requirement.id,
                requirement.required_approval_roles,
                requirement.required_evidence_types,
                requirement.independent_review_profiles,
            )
        )

    result = evaluate(policy, tuple(facts))
    assert result.allowed
    assert {review.status for review in result.reviews} == {"PASS"}

    weakened = list(facts)
    security = next(item for item in weakened if item.id == "security-compliance-review")
    weakened[weakened.index(security)] = fact(
        security.id,
        [role for role in security.approval_roles if role != "governance-owner"],
        security.evidence_types,
        security.independent_review_profiles,
    )
    result = evaluate(policy, tuple(weakened))
    assert not result.allowed
    security_result = next(review for review in result.reviews if review.id == "security-compliance-review")
    assert any(blocker["code"] == "enterprise-review.approval" for blocker in security_result.blockers)


def test_unknown_profile_and_review_fact_fail_with_stable_codes():
    with pytest.raises(EnterpriseReviewError) as exc:
        load_policy("missing")
    assert exc.value.code == "enterprise-review.profile_unknown"

    with pytest.raises(EnterpriseReviewError) as exc:
        evaluate(
            load_policy("starter"),
            (fact("unknown-review", [], []),),
        )
    assert exc.value.code == "enterprise-review.fact_unknown"


def test_duplicate_review_fact_fails_closed():
    policy = load_policy("starter")
    duplicate = fact("business-review", ["product-owner"], ["business-decision"])
    with pytest.raises(EnterpriseReviewError) as exc:
        evaluate(policy, (duplicate, duplicate))
    assert exc.value.code == "enterprise-review.fact_duplicate"
