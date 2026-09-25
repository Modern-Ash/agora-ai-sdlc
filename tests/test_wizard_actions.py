from types import SimpleNamespace

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.wizard_actions import execute_in_session_action, next_in_session_action


def final_acceptance_decision() -> GuidedDecision:
    return GuidedDecision(
        swarm="delivery",
        work="issue-26",
        title="Deliver issue",
        method="ai-sdlc",
        actor="project:product-owner",
        role="product-owner",
        state="operations",
        target="completed",
        gate="completion",
        blockers=("unsatisfied=[source-issue]",),
        messages=("Complete criteria.",),
        missing_artifacts=(),
        missing_evidence=(),
        missing_approvals=(),
        unsatisfied_criteria=("source-issue",),
        git_issues=(),
        clarification_issues=(),
        ready_for_human_approval=False,
        ready_to_transition=False,
        criterion_statuses=(("source-issue", ("elaborated", "designed", "built", "verified", "deployed")),),
    )


def test_final_acceptance_records_accepted_stage_with_responsible_actor(tmp_path):
    calls = []

    class Workspace:
        def satisfy_criterion(self, data, criterion_id, *, stage=None):
            calls.append(
                SimpleNamespace(
                    swarm=data.swarm_id,
                    work=data.work_id,
                    actor=data.actor_id,
                    criterion=criterion_id,
                    stage=stage,
                )
            )

    decision = final_acceptance_decision()

    assert next_in_session_action(decision) == "accept-criteria"

    result = execute_in_session_action(
        tmp_path,
        decision,
        workspace_factory=lambda cwd: Workspace(),
    )

    assert result.kind == "criteria_accepted"
    assert result.details == (("count", 1),)
    assert len(calls) == 1
    assert calls[0].swarm == "delivery"
    assert calls[0].work == "issue-26"
    assert calls[0].actor == "project:product-owner"
    assert calls[0].criterion == "source-issue"
    assert calls[0].stage == "accepted"


def test_verified_criterion_records_deployed_stage_with_assigned_ai_developer(tmp_path):
    calls = []

    class Workspace:
        def satisfy_criterion(self, data, criterion_id, *, stage=None):
            calls.append(
                SimpleNamespace(
                    swarm=data.swarm_id,
                    work=data.work_id,
                    actor=data.actor_id,
                    criterion=criterion_id,
                    stage=stage,
                )
            )

    decision = final_acceptance_decision()
    decision = GuidedDecision(
        **{
            **decision.snapshot(),
            "criterion_statuses": (("source-issue", ("elaborated", "designed", "built", "verified")),),
            "developer_actor": "project:ai-developer",
            "developer_actor_kind": "ai-agent",
        }
    )

    assert next_in_session_action(decision) == "mark-deployed"

    result = execute_in_session_action(
        tmp_path,
        decision,
        workspace_factory=lambda cwd: Workspace(),
    )

    assert result.kind == "criteria_deployed"
    assert result.details == (("count", 1), ("actor", "project:ai-developer"))
    assert len(calls) == 1
    assert calls[0].actor == "project:ai-developer"
    assert calls[0].criterion == "source-issue"
    assert calls[0].stage == "deployed"


def test_construction_criterion_progression_records_next_stage_with_developer(tmp_path):
    calls = []

    class Workspace:
        def satisfy_criterion(self, data, criterion_id, *, stage=None):
            calls.append((data.actor_id, criterion_id, stage))

    decision = GuidedDecision(
        swarm="delivery",
        work="issue-14",
        title="Deliver issue",
        method="ai-sdlc",
        actor="project:ai-codex",
        role="developer",
        state="construction",
        target="operations",
        gate="construction-verified",
        blockers=("unsatisfied=[source-issue]",),
        messages=("Complete criteria.",),
        missing_artifacts=(),
        missing_evidence=(),
        missing_approvals=(),
        unsatisfied_criteria=("source-issue",),
        git_issues=(),
        clarification_issues=(),
        ready_for_human_approval=False,
        ready_to_transition=False,
        criterion_statuses=(("source-issue", ("elaborated", "designed")),),
        developer_actor="project:ai-codex",
        developer_actor_kind="ai-agent",
        next_criterion_stage="built",
    )

    assert next_in_session_action(decision) == "advance-criterion"
    result = execute_in_session_action(tmp_path, decision, workspace_factory=lambda cwd: Workspace())

    assert result.kind == "criterion_stage_advanced"
    assert result.details == (("count", 1), ("stage", "built"), ("actor", "project:ai-codex"))
    assert calls == [("project:ai-codex", "source-issue", "built")]


def test_construction_testing_runs_host_reconciliation_instead_of_llm(monkeypatch, tmp_path):
    decision = GuidedDecision(
        swarm="delivery",
        work="calculator",
        title="Calculator",
        method="ai-sdlc",
        actor="project:ai-opencode",
        role="developer",
        state="construction",
        target="operations",
        gate="construction-verified",
        blockers=("unsatisfied=[source-issue]", "missing-evidence-types=[test-suite]"),
        messages=("Verify implementation.",),
        missing_artifacts=(),
        missing_evidence=("test-suite",),
        missing_approvals=(),
        unsatisfied_criteria=("source-issue",),
        git_issues=(),
        clarification_issues=(),
        criterion_statuses=(("source-issue", ("elaborated", "designed", "built")),),
        developer_actor="project:ai-opencode",
        developer_actor_kind="ai-agent",
    )

    monkeypatch.setattr(
        "agora_ai_sdlc.wizard_actions.persisted_verification_failed",
        lambda root, work: False,
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.wizard_actions.reconcile_construction_execution",
        lambda *args, **kwargs: SimpleNamespace(
            verification_passed=True,
            verification_report=str(tmp_path / "VERIFICATION.json"),
        ),
    )

    assert next_in_session_action(decision, root=tmp_path) == "verify"
    result = execute_in_session_action(tmp_path, decision)

    assert result.kind == "verification_ok"
    assert dict(result.details)["report"].endswith("VERIFICATION.json")


def test_failed_construction_verification_is_not_repeated_locally(monkeypatch, tmp_path):
    decision = GuidedDecision(
        swarm="delivery",
        work="calculator",
        title="Calculator",
        method="ai-sdlc",
        actor="project:ai-opencode",
        role="developer",
        state="construction",
        target="operations",
        gate="construction-verified",
        blockers=("unsatisfied=[source-issue]", "missing-evidence-types=[test-suite]"),
        messages=("Repair tests.",),
        missing_artifacts=(),
        missing_evidence=("test-suite",),
        missing_approvals=(),
        unsatisfied_criteria=("source-issue",),
        git_issues=(),
        clarification_issues=(),
        criterion_statuses=(("source-issue", ("elaborated", "designed", "built")),),
        developer_actor="project:ai-opencode",
        developer_actor_kind="ai-agent",
    )

    monkeypatch.setattr(
        "agora_ai_sdlc.wizard_actions.persisted_verification_failed",
        lambda root, work: True,
    )

    assert next_in_session_action(decision, root=tmp_path) == "review"
