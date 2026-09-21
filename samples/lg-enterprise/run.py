"""Vendor-neutral end-to-end sample for the public LG-style enterprise profile."""

import contextlib
import io
import json
import runpy
from pathlib import Path

from agora_ai_sdlc.compatibility_profiles import load_profile as load_compatibility_profile
from agora_ai_sdlc.conformance.compatibility import evaluate as evaluate_conformance
from agora_ai_sdlc.conformance.lg_enterprise import FACTS_SOURCE, derive_facts
from agora_ai_sdlc.enterprise_controls import ControlFacts
from agora_ai_sdlc.enterprise_controls import evaluate as evaluate_controls
from agora_ai_sdlc.enterprise_controls import load_profile as load_control_profile
from agora_ai_sdlc.enterprise_reviews import ReviewFact, load_policy
from agora_ai_sdlc.enterprise_reviews import evaluate as evaluate_reviews
from agora_ai_sdlc.presentation import render

ROOT = Path(__file__).parents[2]


def _run(name: str) -> dict:
    module = runpy.run_path(str(ROOT / "samples" / name / "run.py"), run_name=f"lg_enterprise_{name}")
    with contextlib.redirect_stdout(io.StringIO()):
        return module["main"]()


def main() -> dict:
    adaptive = _run("adaptive-delivery")
    impact = _run("cross-repo-impact")
    change = _run("change-management")
    knowledge = _run("domain-knowledge")

    review_policy = load_policy("enterprise")
    review_facts = tuple(
        ReviewFact(
            requirement.id,
            requirement.required_approval_roles,
            requirement.required_evidence_types,
            requirement.independent_review_profiles,
        )
        for requirement in review_policy.reviews
    )
    review_result = evaluate_reviews(review_policy, review_facts)

    control_result = evaluate_controls(
        load_control_profile("lg-enterprise"),
        ControlFacts(
            test_classes=("unit", "integration", "acceptance"),
            coverage_obligations=("changed-behavior", "critical-path"),
            reviewer_separation=("distinct-actor",),
            review_evidence=("review-summary", "test-summary"),
        ),
    )

    profile = load_compatibility_profile("lg-enterprise")
    report = evaluate_conformance(profile, derive_facts(ROOT), facts_source=FACTS_SOURCE)
    presentation = render("lg-enterprise", "operations")

    exercised = {
        "adaptive-delivery": adaptive["final_state"] == "completed" and adaptive["validate"] == "ok",
        "cross-repository-impact": impact["final_state"] == "completed",
        "change-configuration-management": change["final_state"] == "completed",
        "domain-knowledge": knowledge["final_state"] == "completed",
        "review-gates": review_result.allowed,
        "enterprise-controls": control_result["allowed"],
        "five-stage-presentation": [stage["id"] for stage in presentation["stages"]]
        == ["initialization", "ideation", "inception", "construction", "operation"],
    }

    summary = {
        "sample": "lg-enterprise",
        "final_state": "completed" if all(exercised.values()) else "failed",
        "validate": "ok" if all(exercised.values()) and report.overall_status in {"PASS", "PARTIAL"} else "failed",
        "profile": profile.id,
        "conformance": report.overall_status,
        "facts_source": report.facts_source,
        "risk_issue_management": next(
            item.status for item in report.results if item.capability == "risk-issue-management"
        ),
        "presentation": presentation,
        "enterprise_reviews_allowed": review_result.allowed,
        "enterprise_controls_allowed": control_result["allowed"],
        "exercised": exercised,
    }
    print(json.dumps(summary, sort_keys=True))
    return summary


if __name__ == "__main__":
    main()
