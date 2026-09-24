"""In-session execution of safe Agora Flow wizard node actions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agora.model import AddApprovalInput, TransitionWorkInput, WorkActorInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.verification import build_verification_report


@dataclass(frozen=True)
class WizardActionResult:
    kind: str
    details: tuple[tuple[str, object], ...] = ()


def _actor_id(decision: GuidedDecision) -> str:
    actor = (decision.actor or "").strip()
    if not actor:
        raise ValueError("The current wizard node has no responsible actor")
    return actor


def next_in_session_action(decision: GuidedDecision) -> str:
    """Return the action Enter should perform at a non-generative node."""

    if (
        decision.state == "operations"
        and decision.target == "completed"
        and decision.gate == "completion"
        and decision.unsatisfied_criteria
        and not (
            decision.missing_artifacts
            or decision.missing_evidence
            or decision.clarification_issues
            or decision.git_issues
        )
    ):
        return "accept-criteria"
    if decision.missing_evidence and not (
        decision.missing_artifacts or decision.clarification_issues or decision.unsatisfied_criteria
    ):
        return "verify"
    if decision.ready_for_human_approval and decision.missing_approvals:
        return "approve"
    if decision.ready_to_transition and decision.target and not decision.blockers:
        return "transition"
    return "review"


def execute_in_session_action(
    root: Path,
    decision: GuidedDecision,
    *,
    workspace_factory=AgoraWorkspace,
) -> WizardActionResult:
    """Execute one explicitly confirmed non-generative wizard action.

    Human approval is recorded only after the user confirms the wizard card.
    Lifecycle transitions are attempted only when Core already reports the node
    ready. The caller must re-inspect Core after every result.
    """

    action = next_in_session_action(decision)
    root = root.resolve()

    if action == "verify":
        report = build_verification_report(
            root,
            swarm=decision.swarm,
            work=decision.work,
            run=True,
            timeout_seconds=300,
            persist=True,
        )
        checks = getattr(report, "checks", ()) or ()
        failed = [
            item
            for item in checks
            if str(getattr(item, "status", getattr(item, "result", ""))).casefold() in {"failed", "failure", "error"}
        ]
        if failed:
            return WizardActionResult("verification_failed", (("count", len(failed)),))
        return WizardActionResult("verification_ok")

    workspace = workspace_factory(cwd=root)

    if action == "accept-criteria":
        actor = _actor_id(decision)
        for criterion in decision.unsatisfied_criteria:
            workspace.satisfy_criterion(
                WorkActorInput(
                    swarm_id=decision.swarm,
                    work_id=decision.work,
                    actor_id=actor,
                ),
                criterion,
                stage="accepted",
            )
        return WizardActionResult("criteria_accepted", (("count", len(decision.unsatisfied_criteria)),))

    if action == "approve":
        actor = _actor_id(decision)
        actor_role = (decision.role or "").strip()
        eligible = [role for role in decision.missing_approvals if not actor_role or role == actor_role]
        if not eligible:
            raise ValueError(
                "The current responsible actor cannot satisfy the outstanding approval role(s): "
                + ", ".join(decision.missing_approvals)
            )
        role = eligible[0]
        workspace.add_approval(
            AddApprovalInput(
                swarm_id=decision.swarm,
                work_id=decision.work,
                actor_id=actor,
                role_id=role,
                note="Explicitly confirmed in Agora Flow wizard",
            )
        )
        return WizardActionResult("approval", (("role", role), ("actor", actor)))

    if action == "transition":
        actor = _actor_id(decision)
        workspace.transition_work(
            TransitionWorkInput(
                swarm_id=decision.swarm,
                work_id=decision.work,
                actor_id=actor,
                target_state=decision.target or "",
            )
        )
        return WizardActionResult("transition", (("target", decision.target or ""),))

    return WizardActionResult("review")
