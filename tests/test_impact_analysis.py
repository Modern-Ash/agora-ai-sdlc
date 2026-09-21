from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.artifacts import check_traceability, parse_artifact
from agora_ai_sdlc.impact_analysis import (
    ImpactAnalysisError,
    affected_repositories,
    assert_approved,
    enterprise_review_evidence,
    parse_impact_analysis,
    summary,
)

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "impact-analysis" / "multi-repo.md"
TRACE = ROOT / "tests" / "fixtures" / "trace"
PLANS = ROOT / "tests" / "fixtures" / "plans"
BOLTS = ROOT / "tests" / "fixtures" / "bolts"


def mutate(fn) -> str:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    end = lines.index("---", 1)
    front = yaml.safe_load("\n".join(lines[1:end]))
    fn(front)
    return "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n" + "\n".join(lines[end + 1 :])


def code(fn) -> str:
    with pytest.raises(ImpactAnalysisError) as exc:
        parse_impact_analysis(mutate(fn))
    return exc.value.code


def test_multi_repo_impact_analysis_parses_and_summarizes():
    analysis = parse_impact_analysis(FIXTURE.read_text(encoding="utf-8"))

    assert affected_repositories(analysis) == ("payments-api", "billing-domain", "customer-web")
    assert {contract.type for contract in analysis.contracts} == {"api", "event"}
    assert any(dependency.status == "unknown" for dependency in analysis.dependencies)
    assert summary(analysis) == {
        "id": "IMA-001",
        "unit": "UOW-001",
        "plan": "PLN-001",
        "bolt_plans": ["BLP-001"],
        "repositories": ["payments-api", "billing-domain", "customer-web"],
        "component_count": 3,
        "contract_types": ["api", "event"],
        "unknown_dependency_count": 1,
        "confidence": "medium",
        "approved": True,
    }
    assert_approved(analysis)
    assert enterprise_review_evidence(analysis) == ("approved-impact-analysis",)


def test_generic_traceability_accepts_unit_plan_bolt_and_impact_analysis():
    artifacts = [
        parse_artifact((TRACE / "intent.md").read_text(encoding="utf-8")),
        parse_artifact((TRACE / "unit.md").read_text(encoding="utf-8")),
        parse_artifact((PLANS / "level1.md").read_text(encoding="utf-8")),
        parse_artifact((BOLTS / "parallel.md").read_text(encoding="utf-8")),
        parse_artifact(FIXTURE.read_text(encoding="utf-8")),
    ]
    check_traceability(artifacts)


def test_at_least_two_repositories_are_required():
    assert code(lambda front: front.update(repositories=front["repositories"][:1])) == "impact.repositories"


def test_repository_ids_are_provider_neutral_slugs_and_refs_are_opaque_uri_like():
    assert code(lambda front: front["repositories"][0].update(id="github.com/org/repo")) == "impact.repository_id"
    assert code(lambda front: front["repositories"][0].update(ref="not a uri")) == "impact.repository_ref"


def test_components_and_contracts_must_reference_declared_repositories():
    assert code(lambda front: front["components"][0].update(repository="missing")) == "impact.repository_unknown"
    assert code(lambda front: front["contracts"][0].update(repository="missing")) == "impact.repository_unknown"


def test_contract_types_are_closed_and_include_api_event_schema():
    assert code(lambda front: front["contracts"][0].update(type="queue")) == "impact.contract_type"

    analysis = parse_impact_analysis(
        mutate(
            lambda front: front["contracts"].append(
                {
                    "type": "schema",
                    "name": "RecurringPayment",
                    "repository": "payments-api",
                    "expected-change": "Add schema revision.",
                }
            )
        )
    )
    assert {contract.type for contract in analysis.contracts} == {"api", "event", "schema"}


def test_unknown_dependency_requires_reason_and_explicit_unknowns():
    def missing_reason(front):
        front["dependencies"][-1]["reason"] = None

    assert code(missing_reason) == "impact.unknown_reason"

    def no_unknowns(front):
        front["unknowns"] = []

    assert code(no_unknowns) == "impact.unknowns"


def test_known_dependency_cannot_use_unknown_direction():
    def fn(front):
        front["dependencies"][0]["direction"] = "unknown"

    assert code(fn) == "impact.dependency_direction"


def test_owner_reviewer_separation_is_required():
    assert code(lambda front: front.update(reviewers=["team-payments"])) == "impact.reviewer_separation"


def test_approval_is_exact_revision_and_approver_must_be_declared_reviewer():
    assert code(lambda front: front.update(revision=3)) == "impact.approval_stale"
    assert code(lambda front: front.update(**{"approved-by": "random-reviewer"})) == "impact.approver_reviewer"


@pytest.mark.parametrize("state", ["pending", "rejected"])
def test_unapproved_analysis_is_not_authorized(state):
    text = mutate(
        lambda front: front.update(
            {
                "approval-state": state,
                "approved-by": None,
                "approved-revision": None,
            }
        )
    )
    analysis = parse_impact_analysis(text)
    with pytest.raises(ImpactAnalysisError) as exc:
        assert_approved(analysis)
    assert exc.value.code == "impact.not_approved"


def test_unit_plan_and_bolt_plan_must_be_trace_bound():
    assert code(lambda front: front.update(**{"traces-to": ["PLN-001", "BLP-001"]})) == "impact.unit_trace"
    assert code(lambda front: front.update(**{"traces-to": ["UOW-001", "BLP-001"]})) == "impact.plan_trace"
    assert code(lambda front: front.update(**{"traces-to": ["UOW-001", "PLN-001"]})) == "impact.bolt_trace"
