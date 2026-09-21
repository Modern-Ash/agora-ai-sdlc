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
                "Gate readiness-approved failed: "
                "missing-artifacts=[readiness-assessment], "
                "missing-evidence-types=[], "
                "missing-approvals=[product-owner], "
                "clarifications=[clarification-not-run]"
            ],
        )
        return [task] if swarm_id in (None, "delivery") else []


def test_guided_projection_translates_core_blockers(monkeypatch, tmp_path):
    monkeypatch.setattr(guided, "AgoraWorkspace", FakeWorkspace)

    decision = guided.inspect_next(tmp_path, swarm="delivery", work="first-work")

    assert decision is not None
    assert decision.state == "readiness"
    assert decision.target == "intent"
    assert decision.role == "product-owner"
    assert decision.messages == (
        "Prepare the required project evidence: readiness-assessment.",
        "Check whether any material clarification remains before proceeding.",
        "Ask the responsible human to approve: product-owner.",
    )

    output = guided.render(decision)
    assert "Before we can continue:" in output
    assert "missing-artifacts" not in output
    assert "Human approvals remain explicit" in output


def test_expert_projection_keeps_raw_core_details(monkeypatch, tmp_path):
    monkeypatch.setattr(guided, "AgoraWorkspace", FakeWorkspace)

    decision = guided.inspect_next(tmp_path)
    output = guided.render(decision, expert=True)

    assert "Governance details:" in output
    assert "missing-artifacts=[readiness-assessment]" in output
    assert "missing-approvals=[product-owner]" in output


def test_guided_projection_can_be_empty(monkeypatch, tmp_path):
    class EmptyWorkspace(FakeWorkspace):
        def next_actions(self, **kwargs):
            return []

    monkeypatch.setattr(guided, "AgoraWorkspace", EmptyWorkspace)
    assert guided.inspect_next(tmp_path) is None
    assert "No governed action currently needs attention." in guided.render(None)
