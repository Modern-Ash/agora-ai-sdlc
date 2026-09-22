from agora_ai_sdlc.iteration_status import IterationStatus, render_status


def sample_status() -> IterationStatus:
    return IterationStatus(
        swarm="delivery",
        work="issue-8",
        title="Define learner journey",
        method="ai-sdlc",
        state="inception",
        target="construction",
        gate="inception-approved",
        actor="project:product-owner",
        role="product-owner",
        base_branch="main",
        work_branch="ai-sdlc/issue-8-learner-journey",
        current_branch="ai-sdlc/issue-8-learner-journey",
        missing_artifacts=(),
        missing_evidence=("independent-review",),
        missing_approvals=("product-owner",),
        unsatisfied_criteria=(),
        git_issues=(),
        clarification_issues=(),
        artifact_kinds=("intent", "plan", "unit-of-work", "bolt-plan"),
        evidence_results=("parser-pass",),
        last_activity="artifact.added: plan PLN-008",
        ready_for_human_approval=True,
        ready_to_transition=False,
    )


def test_human_detail_does_not_change_agent_context():
    status = sample_status()
    before = status.agent_context()

    normal = render_status(status, detail="normal")
    detailed = render_status(status, detail="detail")
    diagnostic = render_status(status, detail="diagnostic")

    assert before == status.agent_context()
    assert len(normal) < len(detailed) < len(diagnostic)
    assert "artifact.added: plan PLN-008" not in normal
    assert "artifact.added: plan PLN-008" in detailed
    assert "Rendering source: local/Core facts only; no LLM call" in diagnostic


def test_agent_context_is_compact_and_excludes_ui_narration():
    context = sample_status().agent_context()

    assert context["schema"] == "agora-ai-sdlc/agent-context/v1"
    assert context["next_action"] == "human-approval"
    assert context["iteration"]["branch"] == "ai-sdlc/issue-8-learner-journey"
    assert context["blockers"]["approvals"] == ["product-owner"]
    assert "last_activity" not in context
    assert "usage" not in context
    assert "title" not in context["iteration"]


def test_unknown_usage_is_rendered_as_unknown_not_zero():
    rendered = render_status(sample_status())

    assert "Usage: unknown" in rendered
    assert "Usage: 0" not in rendered
