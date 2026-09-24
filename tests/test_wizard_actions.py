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
