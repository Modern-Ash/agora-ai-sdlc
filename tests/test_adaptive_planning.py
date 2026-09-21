from pathlib import Path

import pytest

from agora_ai_sdlc.adaptive_planning import (
    AdaptivePlanningError,
    EXPECTED_LIFECYCLE,
    available_pathways,
    effective_depth,
    load_pathway,
    load_policy_set,
    validate_adaptive_plan,
)
from agora_ai_sdlc.plans import parse_plan

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "pathways"


def fixture(name: str):
    return parse_plan((FIXTURES / f"{name}.md").read_text(encoding="utf-8"))


def replace_once(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new, 1)


def test_all_pathways_share_method_pack_020_lifecycle():
    policy = load_policy_set()

    assert policy.method_version == "0.2.0"
    assert policy.lifecycle == EXPECTED_LIFECYCLE
    assert available_pathways() == (
        "brownfield",
        "new-product",
        "refactor",
        "regulated-change",
        "scaling",
        "trivial-change",
    )
    assert {load_pathway(pathway).minimum_depth for pathway in available_pathways()} <= {
        "minimal",
        "standard",
        "comprehensive",
        "regulated",
    }


@pytest.mark.parametrize("depth", ["minimal", "standard"])
def test_trivial_change_can_skip_non_mandatory_design_at_low_depth(depth):
    decision = validate_adaptive_plan(fixture("trivial-change"), "trivial-change", depth=depth)

    assert decision.effective_depth == depth
    assert "domain-design" in decision.skipped_steps
    assert "logical-design" in decision.skipped_steps
    assert "implementation" in decision.mandatory_steps


def test_new_product_executes_full_standard_baseline():
    decision = validate_adaptive_plan(fixture("new-product"), "new-product")

    assert decision.effective_depth == "standard"
    for required in (
        "elaborate-stories",
        "define-nfrs",
        "assess-risks",
        "decompose-units",
        "domain-design",
        "logical-design",
        "implementation",
        "integration-tests",
        "deployment-unit",
    ):
        assert required in decision.executed_steps


def test_brownfield_requires_semantic_elevation_before_construction():
    plan = fixture("brownfield")
    decision = validate_adaptive_plan(plan, "brownfield")
    assert {"brownfield-static-model", "brownfield-dynamic-model"} <= set(decision.mandatory_steps)

    text = (FIXTURES / "brownfield.md").read_text(encoding="utf-8")
    text = replace_once(
        text,
        'id: "brownfield-static-model"\n    decision: "execute"',
        'id: "brownfield-static-model"\n    decision: "skip"',
    )
    with pytest.raises(AdaptivePlanningError) as exc:
        validate_adaptive_plan(parse_plan(text), "brownfield")
    assert exc.value.code == "pathway.mandatory_skip"


def test_regulated_change_cannot_skip_security_or_operational_obligations():
    decision = validate_adaptive_plan(fixture("regulated-change"), "regulated-change")

    assert decision.effective_depth == "regulated"
    for required in ("threat-model", "security-tests", "deployment-unit", "observability", "rollback-readiness"):
        assert required in decision.mandatory_steps

    text = (FIXTURES / "regulated-change.md").read_text(encoding="utf-8")
    text = replace_once(
        text,
        'id: "security-tests"\n    decision: "execute"',
        'id: "security-tests"\n    decision: "skip"',
    )
    with pytest.raises(AdaptivePlanningError) as exc:
        validate_adaptive_plan(parse_plan(text), "regulated-change")
    assert exc.value.code == "pathway.mandatory_skip"


def test_stricter_depth_or_profile_can_only_increase_obligations():
    pathway = load_pathway("trivial-change")
    assert effective_depth(pathway, depth="minimal") == "minimal"
    assert effective_depth(pathway, depth="comprehensive") == "comprehensive"
    assert effective_depth(pathway, adoption_profile="enterprise") == "comprehensive"
    assert effective_depth(pathway, depth="minimal", adoption_profile="regulated") == "regulated"

    with pytest.raises(AdaptivePlanningError) as exc:
        validate_adaptive_plan(fixture("trivial-change"), "trivial-change", adoption_profile="enterprise")
    assert exc.value.code in {"pathway.mandatory_missing", "pathway.mandatory_skip"}


def test_missing_mandatory_step_fails_closed():
    text = (FIXTURES / "trivial-change.md").read_text(encoding="utf-8")
    start = text.index('  - id: "implementation"')
    end = text.index('  - id: "unit-tests"', start)
    plan = parse_plan(text[:start] + text[end:])

    with pytest.raises(AdaptivePlanningError) as exc:
        validate_adaptive_plan(plan, "trivial-change")
    assert exc.value.code == "pathway.mandatory_missing"


def test_unknown_step_is_rejected_by_selected_pathway():
    text = (FIXTURES / "trivial-change.md").read_text(encoding="utf-8")
    text = replace_once(text, 'id: "domain-design"', 'id: "brownfield-static-model"')
    plan = parse_plan(text)

    with pytest.raises(AdaptivePlanningError) as exc:
        validate_adaptive_plan(plan, "trivial-change")
    assert exc.value.code == "pathway.step_not_allowed"


@pytest.mark.parametrize("state", ["pending", "rejected"])
def test_unapproved_or_rejected_plan_cannot_be_authorized(state):
    text = (FIXTURES / "trivial-change.md").read_text(encoding="utf-8")
    text = text.replace('approval-state: "approved"', f'approval-state: "{state}"')
    text = text.replace('approved-by: "project:po"', "approved-by: null")
    text = text.replace("approved-revision: 1", "approved-revision: null")
    plan = parse_plan(text)

    with pytest.raises(AdaptivePlanningError) as exc:
        validate_adaptive_plan(plan, "trivial-change")
    assert exc.value.code == "pathway.plan_not_approved"


def test_unknown_pathway_depth_and_profile_fail_with_stable_codes():
    with pytest.raises(AdaptivePlanningError) as exc:
        load_pathway("nope")
    assert exc.value.code == "pathway.unknown"

    pathway = load_pathway("trivial-change")
    with pytest.raises(AdaptivePlanningError) as exc:
        effective_depth(pathway, depth="nope")
    assert exc.value.code == "pathway.depth"

    with pytest.raises(AdaptivePlanningError) as exc:
        effective_depth(pathway, adoption_profile="nope")
    assert exc.value.code == "pathway.profile"
