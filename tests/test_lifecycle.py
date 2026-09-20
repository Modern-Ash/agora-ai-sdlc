import pytest
from support.lifecycle import Lifecycle


@pytest.fixture
def life(tmp_path, monkeypatch):
    return Lifecycle(tmp_path / "project", tmp_path / "home", monkeypatch)


def test_initial_state_is_readiness(life):
    assert life.state() == "readiness"


def test_happy_path_every_forward_transition(life):
    life.to_intent()
    life.to_inception()
    life.to_construction()
    life.to_operations()
    life.to_completed()
    assert life.state() == "completed"


@pytest.mark.parametrize(
    ("setup", "actor", "target"),
    [
        (lambda life: None, "po", "intent"),
        (lambda life: life.to_intent(), "po", "inception"),
        (lambda life: (life.to_intent(), life.to_inception()), "arch", "construction"),
        (lambda life: (life.to_intent(), life.to_inception(), life.to_construction()), "qa", "operations"),
    ],
)
def test_rejected_gate_does_not_move_state(life, setup, actor, target):
    setup(life)
    before = life.state()
    with pytest.raises(ValueError, match="Gate .* failed"):
        life.move(actor, target)
    assert life.state() == before


@pytest.mark.parametrize(
    ("actor", "target"),
    [("build", "intent"), ("ops", "intent"), ("qa", "intent")],
)
def test_unauthorized_actor_cannot_transition(life, actor, target):
    life.artifact("po", "readiness-assessment")
    life.ws.clarify_work(life.wa("po"), runner="/bin/true")
    life.approve("po", "product-owner")
    with pytest.raises(PermissionError):
        life.move(actor, target)
    assert life.state() == "readiness"


def test_undeclared_transition_is_rejected(life):
    with pytest.raises(ValueError, match="Invalid transition"):
        life.move("po", "completed")
    assert life.state() == "readiness"


def test_rework_inception_to_intent_needs_record_and_keeps_artifacts(life):
    life.to_intent()
    life.to_inception()
    with pytest.raises(ValueError, match="Gate rework-recorded failed"):
        life.move("arch", "intent")
    assert life.state() == "inception"
    life.artifact("arch", "rework-record")
    assert life.move("arch", "intent") == "intent"
    kinds = life.ws.show_work("delivery", "feature").artifact_kinds
    assert {"readiness-assessment", "intent", "rework-record"} <= set(kinds)


def test_rework_construction_to_inception(life):
    life.to_intent()
    life.to_inception()
    life.to_construction()
    life.artifact("arch", "rework-record")
    assert life.move("arch", "inception") == "inception"
    assert "architecture" in life.ws.show_work("delivery", "feature").artifact_kinds


def test_rework_operations_to_construction_keeps_evidence(life):
    life.to_intent()
    life.to_inception()
    life.to_construction()
    life.to_operations()
    with pytest.raises(ValueError, match="Gate rework-recorded failed"):
        life.move("ops", "construction")
    life.artifact("ops", "rework-record")
    assert life.move("ops", "construction") == "construction"
    assert life.ws.show_work("delivery", "feature").evidence_results


def test_completed_has_no_outgoing_transition_and_reopen_makes_new_revision(life):
    life.to_intent()
    life.to_inception()
    life.to_construction()
    life.to_operations()
    life.to_completed()
    with pytest.raises(ValueError, match="Completed work cannot be modified"):
        life.move("po", "operations")
    assert life.state() == "completed"
    before = life.ws.show_work("delivery", "feature").revision
    reopened = life.reopen("po", "customer change request")
    assert reopened.revision == before + 1
    assert reopened.state == "operations"
    assert reopened.status_reason == "customer change request"
    assert reopened.status_by.endswith("po")
    first = life.ws.show_work("delivery", "feature")
    assert first.revision == before + 1


def test_reopen_rejected_before_completion_and_for_non_terminal_roles(life):
    with pytest.raises(ValueError):
        life.reopen("po", "too early")
    life.to_intent()
    life.to_inception()
    life.to_construction()
    life.to_operations()
    life.to_completed()
    with pytest.raises(PermissionError):
        life.reopen("build", "not allowed")
