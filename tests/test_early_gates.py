import pytest
from support.lifecycle import Lifecycle


@pytest.fixture
def life(tmp_path, monkeypatch):
    return Lifecycle(tmp_path / "project", tmp_path / "home", monkeypatch)


def blocked(life, actor, target):
    with pytest.raises(ValueError, match="Gate .* failed") as exc:
        life.move(actor, target)
    assert life.state() != target
    return str(exc.value)


# ---- readiness-approved -------------------------------------------------


def test_readiness_positive(life):
    life.to_intent()


def test_readiness_blockers_are_actionable_and_per_obligation(life):
    message = blocked(life, "po", "intent")
    assert "missing-artifacts=[readiness-assessment]" in message
    assert "clarification-not-run" in message
    life.artifact("po", "readiness-assessment")
    life.clarify()
    assert "missing-approvals=[product-owner]" in blocked(life, "po", "intent")


# ---- intent-framed ------------------------------------------------------


def intent_ready(life, skip=None):
    life.to_intent()
    if skip != "criterion":
        life.stage("po", "elaborated")
    if skip != "artifact":
        life.artifact("po", "intent")
    if skip != "approval":
        life.approve("po", "product-owner")
    if skip != "clarify":
        life.clarify()


def test_intent_positive(life):
    intent_ready(life)
    assert life.move("po", "inception") == "inception"


@pytest.mark.parametrize(
    ("skip", "marker"),
    [
        ("criterion", "required-criterion-stage=elaborated"),
        ("artifact", "missing-artifacts=[intent]"),
        ("clarify", "clarification-inputs-stale"),
    ],
)
def test_intent_one_negative_per_obligation(life, skip, marker):
    intent_ready(life, skip)
    message = blocked(life, "po", "inception")
    assert marker in message
    if skip == "criterion":
        assert "unsatisfied=[value]" in message


# ---- inception-ready ----------------------------------------------------


INCEPTION_ARTIFACTS = (
    "requirements",
    "user-stories",
    "nfr",
    "risk-register",
    "measurement-criteria",
    "plan",
    "unit-of-work",
    "bolt-plan",
)


def inception_ready(life, skip=None):
    intent_ready(life)
    life.move("po", "inception")
    for kind in INCEPTION_ARTIFACTS:
        if skip != kind:
            life.artifact("arch", kind)
    if skip != "architect":
        life.approve("arch", "architect")
    if skip != "product":
        life.approve("po", "product-owner")
    if skip != "clarify":
        life.clarify()


def test_inception_ready_positive(life):
    inception_ready(life)
    assert life.move("arch", "construction") == "construction"


@pytest.mark.parametrize(
    ("skip", "marker"),
    [
        ("user-stories", "missing-artifacts=[user-stories]"),
        ("nfr", "missing-artifacts=[nfr]"),
        ("risk-register", "missing-artifacts=[risk-register]"),
        ("measurement-criteria", "missing-artifacts=[measurement-criteria]"),
        ("plan", "missing-artifacts=[plan]"),
        ("unit-of-work", "missing-artifacts=[unit-of-work]"),
        ("bolt-plan", "missing-artifacts=[bolt-plan]"),
        ("architect", "missing-approvals=[architect]"),
        ("clarify", "clarification-inputs-stale"),
    ],
)
def test_inception_ready_one_negative_per_obligation(life, skip, marker):
    inception_ready(life, skip)
    assert marker in blocked(life, "arch", "construction")


def test_approvals_are_not_gate_scoped_in_core(life):
    """Documents a Core limit: approval records are work-revision scoped rather than gate scoped."""
    intent_ready(life, skip="approval")
    assert life.move("po", "inception") == "inception"


def test_missing_actor_cannot_advance(life):
    inception_ready(life)
    with pytest.raises(PermissionError):
        life.move("po", "construction")
    assert life.state() == "inception"


# ---- revision binding / human ownership --------------------------------


def test_reopen_drops_previous_revision_inputs(life):
    life.to_intent()
    life.to_inception()
    life.to_construction()
    life.to_operations()
    life.to_completed()
    life.reopen("po", "change request")
    work = life.ws.show_work("delivery", "feature")
    assert work.artifact_kinds == [] and work.approval_roles == [] and work.satisfied_criteria == []


@pytest.mark.parametrize("gate", ["readiness-approved", "intent-framed", "inception-ready"])
def test_human_ownership_gates_require_product_owner(gate):
    from test_role_conformance import GATES

    assert "product-owner" in GATES[gate]["required-approval-roles"]
