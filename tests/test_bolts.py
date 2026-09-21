from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.artifacts import check_traceability, parse_artifact
from agora_ai_sdlc.bolts import (
    BoltError,
    assert_can_start,
    check_transition,
    parse_bolt_plan,
    ready_bolts,
    trace,
)

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "bolts" / "parallel.md"
PLANS = ROOT / "tests" / "fixtures" / "plans"
TRACE = ROOT / "tests" / "fixtures" / "trace"


def mutate(fn) -> str:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    end = lines.index("---", 1)
    front = yaml.safe_load("\n".join(lines[1:end]))
    fn(front)
    return "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n" + "\n".join(lines[end + 1 :])


def bolt(front, bolt_id):
    return next(item for item in front["bolts"] if item["id"] == bolt_id)


def code(fn) -> str:
    with pytest.raises(BoltError) as exc:
        parse_bolt_plan(mutate(fn))
    return exc.value.code


def test_golden_parallel_plan_parses_and_reports_parallel_ready_bolts():
    plan = parse_bolt_plan(FIXTURE.read_text(encoding="utf-8"))
    assert [b.id for b in plan.bolts] == ["schema", "api", "ui", "integrate"]
    assert [b.mode for b in plan.bolts] == ["sequential", "parallel", "parallel", "sequential"]
    assert ready_bolts(plan) == ("ui",)


def test_two_parallel_bolts_become_ready_together_once_dependency_completes():
    def fn(front):
        bolt(front, "api")["status"] = "approved"

    plan = parse_bolt_plan(mutate(fn))
    assert ready_bolts(plan) == ("api", "ui")
    assert_can_start(plan, "api")
    assert_can_start(plan, "ui")


def test_trace_links_unit_to_bolts_artifacts_and_evidence():
    summary = trace(parse_bolt_plan(FIXTURE.read_text(encoding="utf-8")))
    assert summary["unit"] == "UOW-001"
    assert summary["bolts"][0] == {
        "id": "schema",
        "mode": "sequential",
        "status": "completed",
        "depends_on": [],
        "artifacts": ["IMP-001"],
        "evidence": ["evidence:schema-tests"],
    }
    assert summary["construction_evidence_complete"] is False


def test_bolt_plan_participates_in_generic_traceability():
    artifacts = [
        parse_artifact((TRACE / "intent.md").read_text(encoding="utf-8")),
        parse_artifact((TRACE / "unit.md").read_text(encoding="utf-8")),
        parse_artifact((PLANS / "level1.md").read_text(encoding="utf-8")),
        parse_artifact(FIXTURE.read_text(encoding="utf-8")),
    ]
    check_traceability(artifacts)


def test_all_bolts_completed_marks_construction_evidence_complete():
    def fn(front):
        for item in front["bolts"]:
            item["status"] = "completed"
            item["evidence"] = ["evidence:" + item["id"]]

    assert trace(parse_bolt_plan(mutate(fn)))["construction_evidence_complete"] is True


def test_parallel_bolts_with_overlapping_writes_conflict():
    assert code(lambda front: bolt(front, "ui").update({"writes": ["src/api/handlers/"]})) == "bolt.parallel_conflict"
    assert code(lambda front: bolt(front, "ui").update({"writes": ["src/api"]})) == "bolt.parallel_conflict"


def test_overlap_is_allowed_when_a_dependency_orders_the_bolts():
    def fn(front):
        bolt(front, "ui")["writes"] = ["src/api/"]
        bolt(front, "ui")["depends-on"] = ["schema", "api"]
        bolt(front, "ui")["status"] = "approved"
        bolt(front, "api")["status"] = "completed"
        bolt(front, "api")["evidence"] = ["evidence:api"]

    parse_bolt_plan(mutate(fn))


def test_sequential_bolt_must_depend_on_every_earlier_bolt():
    assert code(lambda front: bolt(front, "integrate").update({"depends-on": ["schema", "api"]})) == (
        "bolt.sequential_unordered"
    )


def test_dependencies_must_reference_earlier_bolts_so_cycles_are_impossible():
    assert code(lambda front: bolt(front, "schema").update({"depends-on": ["integrate"]})) == "bolt.dependency"


def test_unapproved_plan_allows_only_proposed_bolts():
    def fn(front):
        front.update({"approval-state": "pending", "approved-by": None, "approved-revision": None})

    assert code(fn) == "bolt.not_approved"

    def proposed(front):
        fn(front)
        for item in front["bolts"]:
            item["status"] = "proposed"
            item["evidence"] = []

    plan = parse_bolt_plan(mutate(proposed))
    assert ready_bolts(plan) == ()
    with pytest.raises(BoltError):
        assert_can_start(plan, "schema")


def test_stale_approval_is_rejected():
    assert code(lambda front: front.update({"revision": 3})) == "bolt.approval_stale"


def test_running_or_completed_requires_completed_dependencies():
    assert code(lambda front: bolt(front, "integrate").update({"status": "running"})) == "bolt.dependency_incomplete"


def test_completed_requires_evidence():
    assert code(lambda front: bolt(front, "schema").update({"evidence": []})) == "bolt.evidence_required"


def test_structural_validation():
    assert code(lambda front: bolt(front, "api").update({"mode": "burst"})) == "bolt.mode"
    assert code(lambda front: bolt(front, "api").update({"status": "done"})) == "bolt.status"
    assert code(lambda front: bolt(front, "api").update({"tasks": []})) == "bolt.type"
    assert code(lambda front: bolt(front, "api").update({"id": "schema"})) == "bolt.duplicate_id"
    assert code(lambda front: front.update({"unit": "REQ-001"})) == "bolt.unit"
    assert code(lambda front: front.update({"traces-to": ["PLN-001"]})) == "bolt.unit_trace"
    assert code(lambda front: front.update({"bolts": []})) == "bolt.bolts"
    assert code(lambda front: bolt(front, "api").pop("writes")) == "bolt.entry_fields"


def test_lifecycle_transitions():
    for current, new in [
        ("proposed", "approved"),
        ("approved", "running"),
        ("running", "completed"),
        ("running", "failed"),
    ]:
        check_transition(current, new)
    for current, new in [
        ("proposed", "running"),
        ("approved", "completed"),
        ("completed", "running"),
        ("failed", "running"),
    ]:
        with pytest.raises(BoltError) as exc:
            check_transition(current, new)
        assert exc.value.code == "bolt.transition"
