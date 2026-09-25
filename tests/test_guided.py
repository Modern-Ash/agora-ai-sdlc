from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc import guided


class FakeWorkspace:
    def __init__(self, cwd: Path):
        self.cwd = cwd

    def next_actions(self, *, swarm_id=None, human_only=False, limit=1000):
        assert human_only is False
        assert limit == 1000
        task = SimpleNamespace(
            swarm_id="delivery",
            work_id="first-work",
            actor="project:product-owner",
            role="product-owner",
            state="readiness",
            target_states=["intent"],
            blockers=[
                (
                    "Gate readiness-approved failed: "
                    "missing-artifacts=[readiness-assessment], "
                    "missing-evidence-types=[], "
                    "missing-approvals=[product-owner], "
                    "clarifications=[clarification-not-run]"
                )
            ],
        )
        return [task] if swarm_id in (None, "delivery") else []

    def next_gate_readiness(self, swarm_id, work_id):
        assert swarm_id == "delivery"
        assert work_id == "first-work"
        return {
            "swarm_id": swarm_id,
            "work_id": work_id,
            "state": "readiness",
            "transitions": [
                {
                    "title": "Deliver first governed outcome",
                    "method": "ai-sdlc",
                    "state": "readiness",
                    "target_state": "intent",
                    "gate": {
                        "gate": "readiness-approved",
                        "unsatisfied": [],
                        "missing_artifacts": ["readiness-assessment"],
                        "missing_evidence_types": [],
                        "missing_approvals": ["product-owner"],
                        "git_issues": [],
                    },
                    "ready_for_human_approval": False,
                    "ready_to_complete": False,
                }
            ],
        }


def test_guided_projection_translates_core_blockers(monkeypatch, tmp_path):
    monkeypatch.setattr(guided, "AgoraWorkspace", FakeWorkspace)

    decision = guided.inspect_next(tmp_path, swarm="delivery", work="first-work")

    assert decision is not None
    assert decision.title == "Deliver first governed outcome"
    assert decision.method == "ai-sdlc"
    assert decision.state == "readiness"
    assert decision.target == "intent"
    assert decision.gate == "readiness-approved"
    assert decision.role == "product-owner"
    assert decision.missing_artifacts == ("readiness-assessment",)
    assert decision.missing_approvals == ("product-owner",)
    assert decision.clarification_issues == ("clarification-not-run",)
    assert decision.messages == (
        "Prepare the required project evidence: readiness-assessment.",
        "Resolve the current clarification requirement before proceeding.",
        "Ask the responsible human to approve: product-owner.",
    )

    output = guided.render(decision)
    assert "Objective: Deliver first governed outcome" in output
    assert "Decision gate: readiness-approved" in output
    assert "! Required artifacts" in output
    assert "! Clarifications" in output
    assert "! Human approvals" in output
    assert "missing-artifacts" not in output
    assert "AI may not invent approval" in output
    assert "[P] Prepare with AI" in output


def test_command_bundle_groups_core_primitives(monkeypatch, tmp_path):
    monkeypatch.setattr(guided, "AgoraWorkspace", FakeWorkspace)
    decision = guided.inspect_next(tmp_path)
    assert decision is not None

    commands = guided.command_plan(decision)
    command_text = "\n".join(command for command, _ in commands)

    assert "prepare docs/governance/first-work-readiness.md" in command_text
    assert "agora artifact add" in command_text
    assert "agora work clarify" in command_text
    assert "agora approval add" in command_text
    assert "agora work transition" in command_text
    assert "agora-ai-sdlc continue" not in command_text

    output = guided.render(decision, show_commands=True)
    assert "Underlying command bundle" in output
    assert "Run only after explicit confirmation from the responsible human." in output


def test_expert_projection_keeps_raw_core_details(monkeypatch, tmp_path):
    monkeypatch.setattr(guided, "AgoraWorkspace", FakeWorkspace)

    decision = guided.inspect_next(tmp_path)
    output = guided.render(decision, expert=True)

    assert "Governance details" in output
    assert "missing-artifacts=[readiness-assessment]" in output
    assert "missing-approvals=[product-owner]" in output
    assert "Structured decision" in output
    assert '"gate": "readiness-approved"' in output


def test_guided_projection_can_be_empty(monkeypatch, tmp_path):
    class EmptyWorkspace(FakeWorkspace):
        def next_actions(self, **kwargs):
            return []

    monkeypatch.setattr(guided, "AgoraWorkspace", EmptyWorkspace)
    assert guided.inspect_next(tmp_path) is None
    assert "No governed action currently needs attention." in guided.render(None)


def test_construction_command_bundle_launches_executor_instead_of_rollback():
    decision = guided.GuidedDecision(
        swarm="issue-26-demo",
        work="issue-26",
        title="Deliver GitHub issue #26",
        method="ai-sdlc",
        actor="project:ai-claude",
        role="developer",
        state="construction",
        target="inception",
        gate=None,
        blockers=("construction obligations remain",),
        messages=("Prepare required artifacts.",),
        missing_artifacts=("domain-model", "architecture"),
        missing_evidence=("test-suite",),
        unsatisfied_criteria=("source-issue",),
    )

    commands = guided.command_plan(decision)
    command_text = "\n".join(command for command, _ in commands)

    assert "aisdlc continue --swarm issue-26-demo --work issue-26 --run" in command_text
    assert "--to inception" not in command_text


def test_guided_projection_prefers_forward_transition_over_rework(monkeypatch, tmp_path):
    class MultiTargetWorkspace(FakeWorkspace):
        def next_actions(self, *, swarm_id=None, human_only=False, limit=1000):
            return [
                SimpleNamespace(
                    swarm_id="delivery",
                    work_id="first-work",
                    actor="project:developer",
                    role="developer",
                    state="construction",
                    target_states=["inception", "operations"],
                    blockers=[],
                )
            ]

        def next_gate_readiness(self, swarm_id, work_id):
            return {
                "swarm_id": swarm_id,
                "work_id": work_id,
                "state": "construction",
                "transitions": [
                    {
                        "title": "Rework design",
                        "method": "ai-sdlc",
                        "state": "construction",
                        "target_state": "inception",
                        "gate": {},
                        "ready_for_human_approval": False,
                        "ready_to_complete": True,
                    },
                    {
                        "title": "Advance to operations",
                        "method": "ai-sdlc",
                        "state": "construction",
                        "target_state": "operations",
                        "gate": {"gate": "construction-verified"},
                        "ready_for_human_approval": False,
                        "ready_to_complete": True,
                    },
                ],
            }

        def show_work(self, swarm_id, work_id):
            return SimpleNamespace(artifact_kinds=("domain-model", "architecture", "test-strategy"))

    monkeypatch.setattr(guided, "AgoraWorkspace", MultiTargetWorkspace)

    decision = guided.inspect_next(tmp_path, swarm="delivery", work="first-work")

    assert decision is not None
    assert decision.state == "construction"
    assert decision.target == "operations"
    assert decision.gate == "construction-verified"
    assert decision.ready_to_transition is True


def test_guided_projection_includes_current_criterion_stages(monkeypatch, tmp_path):
    class CriterionWorkspace(FakeWorkspace):
        def next_actions(self, *, swarm_id=None, human_only=False, limit=1000):
            return [
                SimpleNamespace(
                    swarm_id="delivery",
                    work_id="first-work",
                    actor="project:product-owner",
                    role="product-owner",
                    state="operations",
                    target_states=["completed"],
                    blockers=["unsatisfied=[source-issue]"],
                )
            ]

        def next_gate_readiness(self, swarm_id, work_id):
            return {
                "transitions": [
                    {
                        "title": "Complete delivery",
                        "method": "ai-sdlc",
                        "target_state": "completed",
                        "gate": {
                            "gate": "completion",
                            "unsatisfied": ["source-issue"],
                            "missing_artifacts": [],
                            "missing_evidence_types": [],
                            "missing_approvals": [],
                            "git_issues": [],
                        },
                        "ready_for_human_approval": False,
                        "ready_to_complete": False,
                    }
                ]
            }

        def show_work(self, swarm_id, work_id):
            return SimpleNamespace(
                artifact_kinds=("operational-readiness", "rollback-procedure"),
                criterion_statuses={"source-issue": ["elaborated", "designed", "built", "verified", "deployed"]},
            )

        def show_swarm(self, swarm_id):
            return SimpleNamespace(assignments={"developer": "project:ai-developer"})

        def list_actors(self):
            return [
                SimpleNamespace(
                    id="ai-developer",
                    reference="project:ai-developer",
                    kind="ai-agent",
                )
            ]

    monkeypatch.setattr(guided, "AgoraWorkspace", CriterionWorkspace)

    decision = guided.inspect_next(tmp_path, swarm="delivery", work="first-work")

    assert decision is not None
    assert decision.criterion_statuses == (
        ("source-issue", ("elaborated", "designed", "built", "verified", "deployed")),
    )
    assert decision.developer_actor == "project:ai-developer"
    assert decision.developer_actor_kind == "ai-agent"


def test_bare_guided_projection_anchors_to_work_id_from_current_branch(monkeypatch, tmp_path):
    class HistoricalWorkspace(FakeWorkspace):
        def next_actions(self, *, swarm_id=None, human_only=False, limit=1000):
            return [
                SimpleNamespace(
                    swarm_id="old-delivery",
                    work_id="versioned-local-persistence",
                    actor="project:developer",
                    role="developer",
                    state="inception",
                    target_states=["construction"],
                    blockers=["missing-artifacts=[plan]"],
                ),
                SimpleNamespace(
                    swarm_id="issue-15-delivery",
                    work_id="issue-15",
                    actor="project:ai-codex",
                    role="developer",
                    state="construction",
                    target_states=["operations"],
                    blockers=["missing-artifacts=[domain-model]"],
                ),
            ]

        def next_gate_readiness(self, swarm_id, work_id):
            assert swarm_id == "issue-15-delivery"
            assert work_id == "issue-15"
            return {
                "transitions": [
                    {
                        "title": "Deliver GitHub issue #15",
                        "method": "ai-sdlc",
                        "target_state": "operations",
                        "gate": {
                            "gate": "construction-verified",
                            "unsatisfied": [],
                            "missing_artifacts": ["domain-model"],
                            "missing_evidence_types": [],
                            "missing_approvals": [],
                            "git_issues": [],
                        },
                        "ready_for_human_approval": False,
                        "ready_to_complete": False,
                    }
                ]
            }

        def show_work(self, swarm_id, work_id):
            return SimpleNamespace(artifact_kinds=(), criterion_statuses={})

        def show_swarm(self, swarm_id):
            return SimpleNamespace(assignments={"developer": "project:ai-codex"})

        def list_actors(self):
            return [SimpleNamespace(id="ai-codex", reference="project:ai-codex", kind="ai-agent")]

    monkeypatch.setattr(guided, "AgoraWorkspace", HistoricalWorkspace)
    monkeypatch.setattr(guided, "_current_branch", lambda root: "ai-sdlc/issue-15")

    decision = guided.inspect_next(tmp_path)

    assert guided.infer_work_from_current_branch(tmp_path) == "issue-15"
    assert decision is not None
    assert decision.swarm == "issue-15-delivery"
    assert decision.work == "issue-15"
    assert decision.state == "construction"
