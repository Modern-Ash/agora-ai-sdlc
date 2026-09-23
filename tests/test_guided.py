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
    assert "agora-ai-sdlc continue" in command_text

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
