import pytest

from agora_ai_sdlc.enterprise_controls import (
    CLASSIFICATION,
    ControlFacts,
    EnterpriseControlError,
    available_profiles,
    configure,
    evaluate,
    load_profile,
)


def test_packaged_profiles_validate_and_aws_defaults_are_disabled():
    assert available_profiles() == ("aws-original", "lg-enterprise")
    aws = load_profile("aws-original")
    assert not aws.estimation.enabled
    assert not aws.test_design.enabled
    assert not aws.code_review.enabled

    report = evaluate(aws, ControlFacts())
    assert report["allowed"]
    assert {control["status"] for control in report["controls"]} == {"DISABLED"}
    assert {control["requirement"] for control in report["controls"]} == {"enterprise-extension"}


def test_lg_enterprise_enables_test_design_and_code_review_but_estimation_is_optional():
    profile = load_profile("lg-enterprise")
    assert not profile.estimation.enabled and profile.estimation.optional
    assert profile.test_design.enabled and not profile.test_design.optional
    assert profile.code_review.enabled and not profile.code_review.optional
    assert profile.classification == CLASSIFICATION


def test_lg_enterprise_can_enable_neutral_estimation_metrics():
    profile = configure(load_profile("lg-enterprise"), estimation_enabled=True)
    facts = ControlFacts(
        estimation_metrics=("effort-range", "elapsed-time", "ai-cost", "human-review-time"),
        test_classes=("unit", "integration", "acceptance"),
        coverage_obligations=("changed-behavior", "critical-path"),
        reviewer_separation=("distinct-actor",),
        review_evidence=("review-summary", "test-summary"),
    )

    report = evaluate(profile, facts)
    assert report["allowed"]
    assert {control["status"] for control in report["controls"]} == {"PASS"}


def test_test_design_missing_obligation_fails_closed():
    profile = load_profile("lg-enterprise")
    report = evaluate(
        profile,
        ControlFacts(
            test_classes=("unit", "integration", "acceptance"),
            coverage_obligations=("changed-behavior",),
            reviewer_separation=("distinct-actor",),
            review_evidence=("review-summary", "test-summary"),
        ),
    )

    assert not report["allowed"]
    test_design = next(control for control in report["controls"] if control["id"] == "test-design")
    assert test_design["status"] == "FAIL"
    assert test_design["missing"] == ["critical-path"]


def test_code_review_requires_separation_evidence_and_blocks_declared_findings():
    profile = load_profile("lg-enterprise")
    facts = ControlFacts(
        test_classes=("unit", "integration", "acceptance"),
        coverage_obligations=("changed-behavior", "critical-path"),
        reviewer_separation=(),
        review_evidence=("review-summary",),
        blocking_findings=("high",),
    )
    report = evaluate(profile, facts)

    assert not report["allowed"]
    code_review = next(control for control in report["controls"] if control["id"] == "code-review")
    assert code_review["status"] == "FAIL"
    assert code_review["missing"] == ["distinct-actor", "test-summary"]
    assert code_review["blocking_findings"] == ["high"]


def test_conformance_explicitly_marks_enterprise_extension_not_method_requirement():
    profile = load_profile("lg-enterprise")
    report = evaluate(
        profile,
        ControlFacts(
            test_classes=("unit", "integration", "acceptance"),
            coverage_obligations=("changed-behavior", "critical-path"),
            reviewer_separation=("distinct-actor",),
            review_evidence=("review-summary", "test-summary"),
        ),
    )

    assert {control["classification"] for control in report["controls"]} == {"enterprise-extension"}
    assert {control["requirement"] for control in report["controls"]} == {"enterprise-extension"}


def test_unknown_profile_and_invalid_configuration_fail_with_stable_codes():
    with pytest.raises(EnterpriseControlError) as exc:
        load_profile("missing")
    assert exc.value.code == "enterprise-controls.profile_unknown"

    with pytest.raises(EnterpriseControlError) as exc:
        configure(load_profile("aws-original"), estimation_enabled=True)
    assert exc.value.code == "enterprise-controls.config"
