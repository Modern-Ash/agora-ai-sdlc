from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.artifacts import check_traceability, parse_artifact
from agora_ai_sdlc.plans import PlanError, assert_executable, parse_plan, validate_plan_graph

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "plans"
TRACE = ROOT / "tests" / "fixtures" / "trace"


def text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def mutate(name: str, fn) -> str:
    raw = text(name)
    lines = raw.splitlines()
    end = lines.index("---", 1)
    front = yaml.safe_load("\n".join(lines[1:end]))
    fn(front)
    return "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n" + "\n".join(lines[end + 1 :])


def error_code(call):
    with pytest.raises(PlanError) as exc:
        call()
    return exc.value.code


def test_golden_level1_and_level2_parse_validate_and_execute():
    level1 = parse_plan(text("level1.md"))
    level2 = parse_plan(text("level2.md"))

    assert level1.level == 1 and level1.parent_plan is None
    assert level2.level == 2 and level2.parent_plan == "PLN-001"
    assert [step.id for step in level1.steps] == ["elaborate", "design"]
    assert level1.steps[1].dependencies == ("elaborate",)
    assert level2.steps[1].decision == "skip"
    assert_executable(level1)
    assert_executable(level2)
    validate_plan_graph([level1, level2])


def test_generic_artifact_traceability_accepts_plan_artifacts():
    artifacts = [
        parse_artifact((TRACE / "intent.md").read_text(encoding="utf-8")),
        parse_artifact((TRACE / "unit.md").read_text(encoding="utf-8")),
        parse_artifact(text("level1.md")),
        parse_artifact(text("level2.md")),
    ]
    check_traceability(artifacts)


def test_level1_requires_no_parent_and_level_n_requires_parent():
    assert error_code(
        lambda: parse_plan(mutate("level1.md", lambda front: front.update({"parent-plan": "PLN-999"})))
    ) == "plan.parent_level1"
    assert error_code(
        lambda: parse_plan(mutate("level2.md", lambda front: front.update({"parent-plan": None})))
    ) == "plan.parent_required"


def test_parent_intent_and_unit_must_be_traced():
    assert error_code(
        lambda: parse_plan(
            mutate("level1.md", lambda front: front.update({"traces-to": ["UOW-001"]}))
        )
    ) == "plan.intent_trace"
    assert error_code(
        lambda: parse_plan(
            mutate("level1.md", lambda front: front.update({"traces-to": ["INT-001"]}))
        )
    ) == "plan.unit_trace"
    assert error_code(
        lambda: parse_plan(
            mutate(
                "level2.md",
                lambda front: front.update({"traces-to": ["INT-001", "UOW-001"]}),
            )
        )
    ) == "plan.parent_trace"


def test_pending_and_rejected_plans_are_not_executable():
    for state in ("pending", "rejected"):
        raw = mutate(
            "level1.md",
            lambda front, state=state: front.update(
                {"approval-state": state, "approved-by": None, "approved-revision": None}
            ),
        )
        plan = parse_plan(raw)
        assert error_code(lambda plan=plan: assert_executable(plan)) == "plan.not_approved"


def test_approved_plan_requires_accountable_human_and_current_revision():
    assert error_code(
        lambda: parse_plan(mutate("level1.md", lambda front: front.update({"approved-by": None})))
    ) == "plan.approver_required"
    assert error_code(
        lambda: parse_plan(
            mutate(
                "level1.md",
                lambda front: front.update({"revision": 2, "approved-revision": 1}),
            )
        )
    ) == "plan.approval_stale"


def test_reapproval_at_changed_revision_restores_executability():
    plan = parse_plan(
        mutate(
            "level1.md",
            lambda front: front.update({"revision": 2, "approved-revision": 2}),
        )
    )
    assert plan.revision == 2
    assert_executable(plan)


def test_steps_are_ordered_and_dependencies_must_point_backward():
    raw = mutate(
        "level1.md",
        lambda front: front["steps"][0].update({"dependencies": ["design"]}),
    )
    assert error_code(lambda: parse_plan(raw)) == "plan.step_dependency"

    duplicate = mutate(
        "level1.md",
        lambda front: front["steps"][1].update({"id": "elaborate"}),
    )
    assert error_code(lambda: parse_plan(duplicate)) == "plan.step_duplicate"


def test_step_decision_and_rationale_fail_closed():
    assert error_code(
        lambda: parse_plan(
            mutate("level1.md", lambda front: front["steps"][0].update({"decision": "maybe"}))
        )
    ) == "plan.step_decision"
    assert error_code(
        lambda: parse_plan(
            mutate("level1.md", lambda front: front["steps"][0].update({"rationale": ""}))
        )
    ) == "plan.type"


def test_recursive_graph_requires_parent_level_and_same_scope():
    level1 = parse_plan(text("level1.md"))
    missing_parent = parse_plan(text("level2.md"))
    assert error_code(lambda: validate_plan_graph([missing_parent])) == "plan.parent_missing"

    wrong_level = parse_plan(
        mutate("level2.md", lambda front: front.update({"level": 3}))
    )
    assert error_code(lambda: validate_plan_graph([level1, wrong_level])) == "plan.parent_level"

    other_scope = parse_plan(
        mutate(
            "level2.md",
            lambda front: front.update(
                {
                    "intent": "INT-002",
                    "traces-to": ["INT-002", "UOW-001", "PLN-001"],
                }
            ),
        )
    )
    assert error_code(lambda: validate_plan_graph([level1, other_scope])) == "plan.scope_mismatch"


def test_duplicate_plan_ids_rejected_by_graph():
    first = parse_plan(text("level1.md"))
    duplicate = parse_plan(text("level1.md"))
    assert error_code(lambda: validate_plan_graph([first, duplicate])) == "plan.graph_duplicate"
