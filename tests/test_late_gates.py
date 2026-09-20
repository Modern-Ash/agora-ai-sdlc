from pathlib import Path

import pytest
from support.lifecycle import Lifecycle


@pytest.fixture
def life(tmp_path, monkeypatch):
    life = Lifecycle(tmp_path / "project", tmp_path / "home", monkeypatch)
    life.root_path = tmp_path / "project"
    return life


def blocked(life, actor, target):
    with pytest.raises(ValueError, match="Gate .* failed") as exc:
        life.move(actor, target)
    assert life.state() != target
    return str(exc.value)


def at_construction(life):
    life.to_intent()
    life.to_inception()
    life.to_construction()


def build_ready(life, skip=None):
    at_construction(life)
    life.stage("build", "built")
    if skip != "criterion":
        life.stage("qa", "verified")
    for kind in ("implementation-plan", "test-strategy"):
        if skip != kind:
            life.artifact("build", kind)
    if skip != "evidence":
        life.evidence("build", "test-suite")
    if skip != "approval":
        life.approve("qa", "quality-reviewer")


# ---- build-verified -----------------------------------------------------


def test_build_positive(life):
    build_ready(life)
    assert life.move("qa", "operations") == "operations"


@pytest.mark.parametrize(
    ("skip", "marker"),
    [
        ("criterion", "required-criterion-stage=verified"),
        ("implementation-plan", "missing-artifacts=[implementation-plan]"),
        ("test-strategy", "missing-artifacts=[test-strategy]"),
        ("evidence", "missing-evidence-types=[test-suite]"),
        ("approval", "missing-approvals=[quality-reviewer]"),
    ],
)
def test_build_one_negative_per_obligation(life, skip, marker):
    build_ready(life, skip)
    assert marker in blocked(life, "qa", "operations")


def test_failed_test_evidence_blocks_build(life):
    build_ready(life, "evidence")
    life.ws.add_evidence(
        __import__("agora.model", fromlist=["AddEvidenceInput"]).AddEvidenceInput(
            swarm_id="delivery", work_id="feature", actor_id="build", type="test-suite",
            result="failure", artifact_refs=["repo://readiness-assessment.md"],
        )
    )  # fmt: skip
    message = blocked(life, "qa", "operations")
    assert "missing-evidence-types=[test-suite]" in message


# ---- completion ---------------------------------------------------------


def operations(life):
    at_construction(life)
    life.to_operations()


def test_completion_positive_records_acceptance_and_actor(life):
    operations(life)
    life.to_completed()
    approvals = next(Path(life.root_path).rglob("approvals.md")).read_text()
    assert "product-owner" in approvals and "po" in approvals


@pytest.mark.parametrize(
    ("skip", "marker"),
    [
        ("deployment-plan", "missing-artifacts=[deployment-plan]"),
        ("rollback-procedure", "missing-artifacts=[rollback-procedure]"),
        ("operational-readiness", "missing-artifacts=[operational-readiness]"),
        ("criterion", "required-criterion-stage=accepted"),
        ("deployment", "missing-evidence-types=[deployment]"),
        ("security-scan", "missing-evidence-types=[security-scan]"),
    ],
)
def test_completion_one_negative_per_obligation(life, skip, marker):
    operations(life)
    life.prepare_completion(skip)
    assert marker in blocked(life, "po", "completed")


def test_open_blocking_findings_prevent_completion(life):
    from agora.model import AddEvidenceInput

    operations(life)
    life.prepare_completion("security-scan")
    life.ws.add_evidence(
        AddEvidenceInput(
            swarm_id="delivery", work_id="feature", actor_id="ops", type="security-scan",
            result="failure", artifact_refs=["repo://readiness-assessment.md"],
        )
    )  # fmt: skip
    assert "missing-evidence-types=[security-scan]" in blocked(life, "po", "completed")


def test_deployment_evidence_is_bound_to_current_revision(life):
    operations(life)
    life.to_completed()
    life.reopen("po", "change request")
    assert life.state() == "operations"
    assert life.ws.show_work("delivery", "feature").evidence_results == []
    message = blocked(life, "po", "completed")
    assert "missing-evidence-types=[deployment, security-scan]" in message
    assert "missing-artifacts=[deployment-plan, rollback-procedure, operational-readiness]" in message
