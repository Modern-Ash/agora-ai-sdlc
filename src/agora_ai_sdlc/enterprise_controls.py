"""Provider-neutral enterprise delivery controls.

These controls are declarative flavor-level extensions. They evaluate supplied
facts and never transition Agora Core lifecycle state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import yaml

from agora_ai_sdlc.depth_profiles import asset_root

SCHEMA = "agora-ai-sdlc/enterprise-controls-profile/v1"
CLASSIFICATION = "enterprise-extension"
CONTROL_IDS = ("estimation", "test-design", "code-review")
ESTIMATION_METRICS = {"effort-range", "elapsed-time", "ai-cost", "human-review-time"}
TEST_CLASSES = {"unit", "integration", "acceptance", "contract", "system", "performance", "security"}
COVERAGE_OBLIGATIONS = {"changed-behavior", "critical-path", "risk-based", "requirements-traceability"}
REVIEW_SEPARATION = {"distinct-actor", "distinct-runtime", "distinct-provider", "human-final"}
REVIEW_EVIDENCE = {"review-summary", "test-summary", "security-summary", "traceability-summary"}
FINDING_SEVERITIES = {"critical", "high", "medium", "low"}


class EnterpriseControlError(ValueError):
    """Stable validation error for enterprise delivery controls."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class EstimationControl:
    enabled: bool
    optional: bool
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class TestDesignControl:
    enabled: bool
    optional: bool
    required_test_classes: tuple[str, ...]
    coverage_obligations: tuple[str, ...]


@dataclass(frozen=True)
class CodeReviewControl:
    enabled: bool
    optional: bool
    reviewer_separation: tuple[str, ...]
    required_evidence: tuple[str, ...]
    blocking_findings: tuple[str, ...]


@dataclass(frozen=True)
class EnterpriseControlProfile:
    id: str
    compatibility_profile: str
    classification: str
    estimation: EstimationControl
    test_design: TestDesignControl
    code_review: CodeReviewControl


@dataclass(frozen=True)
class ControlFacts:
    estimation_metrics: tuple[str, ...] = ()
    test_classes: tuple[str, ...] = ()
    coverage_obligations: tuple[str, ...] = ()
    reviewer_separation: tuple[str, ...] = ()
    review_evidence: tuple[str, ...] = ()
    blocking_findings: tuple[str, ...] = ()


def _strings(value: object, field: str, allowed: set[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise EnterpriseControlError("enterprise-controls.type", f"{field} must be a list of strings")
    if len(set(value)) != len(value):
        raise EnterpriseControlError("enterprise-controls.duplicate", f"{field} contains duplicates")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise EnterpriseControlError(
            "enterprise-controls.value",
            f"{field} contains unsupported values: {', '.join(unknown)}",
        )
    return tuple(value)


def _control(data: dict, control_id: str) -> dict:
    raw = data.get(control_id)
    if not isinstance(raw, dict):
        raise EnterpriseControlError("enterprise-controls.control", f"{control_id} must be a mapping")
    return raw


def parse_profile(contents: str) -> EnterpriseControlProfile:
    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as error:
        raise EnterpriseControlError("enterprise-controls.syntax", "profile is not valid YAML") from error
    if not isinstance(data, dict):
        raise EnterpriseControlError("enterprise-controls.syntax", "profile must be a mapping")
    expected = {"schema", "id", "compatibility_profile", "classification", "controls", "metadata"}
    if set(data) != expected:
        raise EnterpriseControlError("enterprise-controls.fields", "profile fields do not match v1 contract")
    if data.get("schema") != SCHEMA:
        raise EnterpriseControlError("enterprise-controls.schema", f"unsupported schema {data.get('schema')!r}")
    profile_id = data.get("id")
    compatibility = data.get("compatibility_profile")
    if profile_id not in {"aws-original", "lg-enterprise"} or compatibility != profile_id:
        raise EnterpriseControlError("enterprise-controls.profile", "profile id must match its compatibility profile")
    if data.get("classification") != CLASSIFICATION:
        raise EnterpriseControlError("enterprise-controls.classification", f"classification must be {CLASSIFICATION}")
    if not isinstance(data.get("metadata"), dict):
        raise EnterpriseControlError("enterprise-controls.metadata", "metadata must be a mapping")

    controls = data.get("controls")
    if not isinstance(controls, dict) or set(controls) != set(CONTROL_IDS):
        raise EnterpriseControlError(
            "enterprise-controls.controls",
            "controls must declare estimation/test-design/code-review",
        )

    estimation = _control(controls, "estimation")
    if set(estimation) != {"enabled", "optional", "metrics"}:
        raise EnterpriseControlError("enterprise-controls.fields", "estimation fields do not match v1 contract")
    if not isinstance(estimation["enabled"], bool) or not isinstance(estimation["optional"], bool):
        raise EnterpriseControlError("enterprise-controls.type", "estimation enabled/optional must be boolean")

    test_design = _control(controls, "test-design")
    if set(test_design) != {"enabled", "optional", "required-test-classes", "coverage-obligations"}:
        raise EnterpriseControlError("enterprise-controls.fields", "test-design fields do not match v1 contract")
    if not isinstance(test_design["enabled"], bool) or not isinstance(test_design["optional"], bool):
        raise EnterpriseControlError("enterprise-controls.type", "test-design enabled/optional must be boolean")

    code_review = _control(controls, "code-review")
    if set(code_review) != {
        "enabled",
        "optional",
        "reviewer-separation",
        "required-evidence",
        "blocking-findings",
    }:
        raise EnterpriseControlError("enterprise-controls.fields", "code-review fields do not match v1 contract")
    if not isinstance(code_review["enabled"], bool) or not isinstance(code_review["optional"], bool):
        raise EnterpriseControlError("enterprise-controls.type", "code-review enabled/optional must be boolean")

    parsed = EnterpriseControlProfile(
        profile_id,
        compatibility,
        CLASSIFICATION,
        EstimationControl(
            estimation["enabled"],
            estimation["optional"],
            _strings(estimation["metrics"], "estimation.metrics", ESTIMATION_METRICS),
        ),
        TestDesignControl(
            test_design["enabled"],
            test_design["optional"],
            _strings(
                test_design["required-test-classes"],
                "test-design.required-test-classes",
                TEST_CLASSES,
            ),
            _strings(
                test_design["coverage-obligations"],
                "test-design.coverage-obligations",
                COVERAGE_OBLIGATIONS,
            ),
        ),
        CodeReviewControl(
            code_review["enabled"],
            code_review["optional"],
            _strings(
                code_review["reviewer-separation"],
                "code-review.reviewer-separation",
                REVIEW_SEPARATION,
            ),
            _strings(
                code_review["required-evidence"],
                "code-review.required-evidence",
                REVIEW_EVIDENCE,
            ),
            _strings(
                code_review["blocking-findings"],
                "code-review.blocking-findings",
                FINDING_SEVERITIES,
            ),
        ),
    )
    if profile_id == "aws-original" and any(
        control.enabled for control in (parsed.estimation, parsed.test_design, parsed.code_review)
    ):
        raise EnterpriseControlError(
            "enterprise-controls.aws_default",
            "AWS-original enterprise controls must remain disabled by default",
        )
    return parsed


def available_profiles() -> tuple[str, ...]:
    root = asset_root("profiles") / "enterprise-controls"
    return tuple(path.stem for path in sorted(root.glob("*.yaml"))) if root.is_dir() else ()


def load_profile(profile_id: str) -> EnterpriseControlProfile:
    if profile_id not in {"aws-original", "lg-enterprise"}:
        raise EnterpriseControlError("enterprise-controls.profile_unknown", f"unknown profile {profile_id!r}")
    path = asset_root("profiles") / "enterprise-controls" / f"{profile_id}.yaml"
    if not path.is_file():
        raise EnterpriseControlError("enterprise-controls.profile_unknown", f"unknown profile {profile_id!r}")
    profile = parse_profile(path.read_text(encoding="utf-8"))
    if profile.id != profile_id:
        raise EnterpriseControlError("enterprise-controls.profile_mismatch", "profile id does not match file")
    return profile


def configure(
    profile: EnterpriseControlProfile,
    *,
    estimation_enabled: bool | None = None,
) -> EnterpriseControlProfile:
    """Apply the v1 project-level override: optional estimation enablement."""
    if estimation_enabled is None:
        return profile
    if not isinstance(estimation_enabled, bool):
        raise EnterpriseControlError("enterprise-controls.config", "estimation_enabled must be boolean")
    if estimation_enabled and (not profile.estimation.optional or not profile.estimation.metrics):
        raise EnterpriseControlError("enterprise-controls.config", "estimation is not configurable in this profile")
    return replace(profile, estimation=replace(profile.estimation, enabled=estimation_enabled))


def _missing(required: tuple[str, ...], actual: tuple[str, ...]) -> list[str]:
    return sorted(set(required) - set(actual))


def evaluate(profile: EnterpriseControlProfile, facts: ControlFacts) -> dict:
    """Evaluate configured controls and return deterministic conformance evidence."""
    results: list[dict] = []

    if profile.estimation.enabled:
        missing = _missing(profile.estimation.metrics, facts.estimation_metrics)
        results.append(
            {
                "id": "estimation",
                "classification": CLASSIFICATION,
                "requirement": "enterprise-extension",
                "status": "PASS" if not missing else "FAIL",
                "missing": missing,
            }
        )
    else:
        results.append(
            {
                "id": "estimation",
                "classification": CLASSIFICATION,
                "requirement": "enterprise-extension",
                "status": "DISABLED",
                "missing": [],
            }
        )

    if profile.test_design.enabled:
        missing_classes = _missing(profile.test_design.required_test_classes, facts.test_classes)
        missing_coverage = _missing(profile.test_design.coverage_obligations, facts.coverage_obligations)
        results.append(
            {
                "id": "test-design",
                "classification": CLASSIFICATION,
                "requirement": "enterprise-extension",
                "status": "PASS" if not missing_classes and not missing_coverage else "FAIL",
                "missing": missing_classes + missing_coverage,
            }
        )
    else:
        results.append(
            {
                "id": "test-design",
                "classification": CLASSIFICATION,
                "requirement": "enterprise-extension",
                "status": "DISABLED",
                "missing": [],
            }
        )

    if profile.code_review.enabled:
        missing_separation = _missing(profile.code_review.reviewer_separation, facts.reviewer_separation)
        missing_evidence = _missing(profile.code_review.required_evidence, facts.review_evidence)
        blocking = sorted(set(profile.code_review.blocking_findings) & set(facts.blocking_findings))
        status = "PASS" if not missing_separation and not missing_evidence and not blocking else "FAIL"
        results.append(
            {
                "id": "code-review",
                "classification": CLASSIFICATION,
                "requirement": "enterprise-extension",
                "status": status,
                "missing": missing_separation + missing_evidence,
                "blocking_findings": blocking,
            }
        )
    else:
        results.append(
            {
                "id": "code-review",
                "classification": CLASSIFICATION,
                "requirement": "enterprise-extension",
                "status": "DISABLED",
                "missing": [],
                "blocking_findings": [],
            }
        )

    return {
        "schema": "agora-ai-sdlc/enterprise-controls-conformance/v1",
        "profile": profile.id,
        "compatibility_profile": profile.compatibility_profile,
        "allowed": not any(item["status"] == "FAIL" for item in results),
        "controls": results,
    }
