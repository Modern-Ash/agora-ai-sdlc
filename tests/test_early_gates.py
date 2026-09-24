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


# ---- architecture-approved ---------------------------------------------


def architecture_ready(life, skip=None):
    intent_ready(life)
    life.move("po", "inception")
    if skip != "criterion":
        life.stage("arch", "designed")
    if skip != "architecture":
        life.artifact("arch", "architecture")
    if skip != "requirements":
        life.artifact("arch", "requirements")
    if skip != "architect":
        life.approve("arch", "architect")
    if skip != "product":
        life.approve("po", "product-owner")
    if skip != "clarify":
        life.clarify()


def test_architecture_positive(life):
    architecture_ready(life)
    assert life.move("arch", "construction") == "construction"


@pytest.mark.parametrize(
    ("skip", "marker"),
    [
        ("criterion", "required-criterion-stage=designed"),
        ("architecture", "missing-artifacts=[architecture]"),
        ("requirements", "missing-artifacts=[requirements]"),
        ("architect", "missing-approvals=[architect]"),
        ("clarify", "clarification-inputs-stale"),
    ],
)
def test_architecture_one_negative_per_obligation(life, skip, marker):
    architecture_ready(life, skip)
    assert marker in blocked(life, "arch", "construction")


def test_approvals_are_not_gate_scoped_in_core(life):
    """Documents a Core 0.8.2 limit: a role's approval given at an earlier gate satisfies later gates in the
    same revision, so a fresh product-owner approval per gate is a convention, not enforced."""
    intent_ready(life, skip="approval")  # only the readiness-gate approval exists
    assert life.move("po", "inception") == "inception"


def test_missing_actor_cannot_advance(life):
    architecture_ready(life)
    with pytest.raises(PermissionError):
        life.move("po", "construction")  # product-owner is not a transition role for this edge
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


@pytest.mark.parametrize("gate", ["readiness-approved", "intent-framed", "architecture-approved"])
def test_human_ownership_gates_require_product_owner(gate):
    from test_role_conformance import GATES

    assert "product-owner" in GATES[gate]["required-approval-roles"]
