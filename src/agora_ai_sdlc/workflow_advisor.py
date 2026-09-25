"""Proactive workflow advice for the guided AI-SDLC experience.

Laya is used as a local, cheap classifier below the UX. Agora Core remains the
source of truth and all authority-bearing steps remain explicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.delivery_submission import pull_request_delivery_enabled
from agora_ai_sdlc.execution_bundle import build_execution_bundle
from agora_ai_sdlc.execution_decisions import advise_execution
from agora_ai_sdlc.executor_recovery import ExecutorRecoveryChoice, recovery_choices
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.laya_provider import LayaDecisionProvider, LayaUnavailable
from agora_ai_sdlc.local_delivery import local_artifacts_delivery_enabled


@dataclass(frozen=True)
class WorkflowAdvice:
    action: str
    summary: str
    needs_runtime: bool
    reasoning_tier: str | None = None
    confidence: float | None = None
    source: str = "deterministic"
    recommended_runtime: ExecutorRecoveryChoice | None = None
    escalation_required: bool = False
    context_candidates: int = 0
    context_selected: int = 0
    context_tokens_before: int = 0
    context_tokens_after: int = 0
    context_tokens_saved: int = 0
    context_reduction_ratio: float = 0.0
    context_escalated: tuple[str, ...] = ()
    security_review: str | None = None
    security_confidence: float | None = None
    change_risk: str | None = None
    change_risk_confidence: float | None = None
    validation_focus: str | None = None
    validation_focus_confidence: float | None = None

    def snapshot(self) -> dict:
        data = asdict(self)
        if self.recommended_runtime is not None:
            data["recommended_runtime"] = {
                "agent": self.recommended_runtime.agent,
                "model": self.recommended_runtime.model,
                "label": self.recommended_runtime.label,
            }
        return data


def _free_runtime(root: Path) -> ExecutorRecoveryChoice | None:
    """Prefer an already available local/free executor without prompting."""

    try:
        choices = recovery_choices(root)
    except (OSError, RuntimeError, ValueError):
        return None
    for marker in ("[local]", "[free]"):
        for choice in choices:
            if marker in choice.label.casefold():
                return choice
    return None


def advise_workflow(
    root: Path,
    decision: GuidedDecision,
    *,
    confidence_threshold: float = 0.90,
) -> WorkflowAdvice:
    """Choose the simplest next interaction.

    Keep the pre-confirmation Laya pass lightweight. Expensive per-file context
    selection is deferred to execution after the user explicitly confirms.
    """

    # Authority-bearing decisions never go through Laya.
    if decision.ready_for_human_approval and decision.missing_approvals:
        return WorkflowAdvice(
            action="approve",
            summary="Review the completed evidence and explicitly confirm the required human approval in this wizard.",
            needs_runtime=False,
        )

    # Final acceptance of already-delivered criteria is a human authority boundary,
    # not another generative preparation step.
    criterion_statuses = dict(decision.criterion_statuses)
    pending_deployment = tuple(
        item for item in decision.unsatisfied_criteria if "deployed" not in criterion_statuses.get(item, ())
    )

    pull_request_delivery = (
        decision.state == "operations"
        and decision.target == "completed"
        and decision.gate == "completion"
        and bool(pending_deployment)
        and all("verified" in criterion_statuses.get(item, ()) for item in pending_deployment)
        and decision.developer_actor
        and decision.developer_actor_kind == "ai-agent"
        and set(decision.missing_evidence).issubset({"deployment"})
        and not (decision.missing_artifacts or decision.clarification_issues or decision.git_issues)
        and pull_request_delivery_enabled(root)
    )
    if pull_request_delivery:
        return WorkflowAdvice(
            action="submit-pr",
            summary=(
                "Publish the Work-owned change set as a governed Pull Request and record the PR as deployment evidence."
            ),
            needs_runtime=False,
        )

    local_artifact_delivery = (
        decision.state == "operations"
        and decision.target == "completed"
        and decision.gate == "completion"
        and bool(pending_deployment)
        and all("verified" in criterion_statuses.get(item, ()) for item in pending_deployment)
        and decision.developer_actor
        and decision.developer_actor_kind == "ai-agent"
        and set(decision.missing_evidence).issubset({"deployment"})
        and not (decision.missing_artifacts or decision.clarification_issues or decision.git_issues)
        and local_artifacts_delivery_enabled(root)
    )
    if local_artifact_delivery:
        return WorkflowAdvice(
            action="publish-local-artifacts",
            summary="Publish generated product files and AI-SDLC artifacts to the local output directory.",
            needs_runtime=False,
        )
    final_criterion_deployment = (
        decision.state == "operations"
        and decision.target == "completed"
        and decision.gate == "completion"
        and bool(pending_deployment)
        and all("verified" in criterion_statuses.get(item, ()) for item in pending_deployment)
        and not (
            decision.missing_artifacts
            or decision.missing_evidence
            or decision.clarification_issues
            or decision.git_issues
        )
    )
    if final_criterion_deployment:
        if decision.developer_actor and decision.developer_actor_kind == "ai-agent":
            return WorkflowAdvice(
                action="mark-deployed",
                summary="Record the already-evidenced deployment stage with the assigned AI developer, then re-read Core.",
                needs_runtime=False,
            )
        return WorkflowAdvice(
            action="review",
            summary="The remaining deployed criterion stage requires the assigned developer actor; stay at the human boundary.",
            needs_runtime=False,
        )

    final_criterion_acceptance = (
        decision.state == "operations"
        and decision.target == "completed"
        and decision.gate == "completion"
        and bool(decision.unsatisfied_criteria)
        and all("deployed" in criterion_statuses.get(item, ()) for item in decision.unsatisfied_criteria)
        and not (
            decision.missing_artifacts
            or decision.missing_evidence
            or decision.clarification_issues
            or decision.git_issues
        )
    )
    if final_criterion_acceptance:
        return WorkflowAdvice(
            action="accept-criteria",
            summary="Explicitly accept the completed criteria as Product Owner, then re-read Core.",
            needs_runtime=False,
        )

    criterion_progression = (
        decision.state == "construction"
        and bool(decision.unsatisfied_criteria)
        and decision.next_criterion_stage in {"built", "verified"}
        and decision.developer_actor
        and decision.developer_actor_kind == "ai-agent"
        and not (
            decision.missing_artifacts
            or decision.missing_evidence
            or decision.clarification_issues
            or decision.git_issues
        )
    )
    if criterion_progression:
        return WorkflowAdvice(
            action="advance-criterion",
            summary=(
                f"Record the evidenced {decision.next_criterion_stage} criterion stage with the assigned developer, "
                "then re-read Core."
            ),
            needs_runtime=False,
        )

    # Verification is deterministic and cheaper than any model call.
    if decision.missing_evidence and not (
        decision.missing_artifacts or decision.clarification_issues or decision.unsatisfied_criteria
    ):
        return WorkflowAdvice(
            action="verify",
            summary="Run deterministic verification now, persist the evidence, then re-read Core automatically.",
            needs_runtime=False,
        )

    needs_preparation = bool(
        decision.missing_artifacts or decision.clarification_issues or decision.unsatisfied_criteria or decision.blocked
    )
    if not needs_preparation:
        if decision.ready_to_transition and decision.target and not decision.blockers:
            return WorkflowAdvice(
                action="transition",
                summary=f"Advance the Work to {decision.target} and continue from the next Core node.",
                needs_runtime=False,
            )
        return WorkflowAdvice(
            action="review",
            summary="The governed step is ready for the responsible actor; inspect the evidence at this node.",
            needs_runtime=False,
        )

    tier = None
    confidence = None
    source = "deterministic"
    escalation = False
    context_candidates = 0
    context_selected = 0
    context_tokens_before = 0
    context_tokens_after = 0
    context_tokens_saved = 0
    context_reduction_ratio = 0.0
    context_escalated: tuple[str, ...] = ()
    security_review = None
    security_confidence = None
    change_risk = None
    change_risk_confidence = None
    validation_focus = None
    validation_focus_confidence = None

    try:
        bundle = build_execution_bundle(
            root,
            swarm=decision.swarm,
            work=decision.work,
            persist=False,
        )
        provider = LayaDecisionProvider()
        evaluated = advise_execution(
            bundle,
            provider=provider,
            confidence_threshold=confidence_threshold,
        )
        answer = evaluated.result.answers.get("reasoning_tier")
        if answer is not None:
            tier = str(answer.value)
            confidence = answer.confidence
            source = "laya"
            escalation = "reasoning_tier" in evaluated.escalated
        security = evaluated.result.answers.get("security_review")
        if security is not None:
            security_review = str(security.value)
            security_confidence = security.confidence
        risk = evaluated.result.answers.get("change_risk")
        if risk is not None:
            change_risk = str(risk.value)
            change_risk_confidence = risk.confidence
        focus = evaluated.result.answers.get("validation_focus")
        if focus is not None:
            validation_focus = str(focus.value)
            validation_focus_confidence = focus.confidence

    except (LayaUnavailable, OSError, RuntimeError, ValueError):
        pass

    recommended = None
    # Token-saving default: automatically preselect only local/free executors.
    # Paid/configured providers still require the user's explicit runtime choice.
    if source == "laya" and tier in {"local", "standard"} and not escalation:
        recommended = _free_runtime(root)

    if tier == "human" and not escalation:
        return WorkflowAdvice(
            action="review",
            summary="The next step needs human judgement; stay in this wizard and inspect the evidence/options.",
            needs_runtime=False,
            reasoning_tier=tier,
            confidence=confidence,
            source=source,
            context_candidates=context_candidates,
            context_selected=context_selected,
            context_tokens_before=context_tokens_before,
            context_tokens_after=context_tokens_after,
            context_tokens_saved=context_tokens_saved,
            context_reduction_ratio=context_reduction_ratio,
            context_escalated=context_escalated,
            security_review=security_review,
            security_confidence=security_confidence,
            change_risk=change_risk,
            change_risk_confidence=change_risk_confidence,
            validation_focus=validation_focus,
            validation_focus_confidence=validation_focus_confidence,
        )

    if escalation:
        summary = "The local decision model is uncertain; prepare with an agent and keep the normal review boundary."
    elif recommended is not None:
        summary = "Prepare the missing non-authoritative work with the available local/free assistant."
    else:
        summary = "Prepare the missing non-authoritative work; choose an assistant only when execution starts."

    return WorkflowAdvice(
        action="prepare",
        summary=summary,
        needs_runtime=True,
        reasoning_tier=tier,
        confidence=confidence,
        source=source,
        recommended_runtime=recommended,
        escalation_required=escalation,
        context_candidates=context_candidates,
        context_selected=context_selected,
        context_tokens_before=context_tokens_before,
        context_tokens_after=context_tokens_after,
        context_tokens_saved=context_tokens_saved,
        context_reduction_ratio=context_reduction_ratio,
        context_escalated=context_escalated,
        security_review=security_review,
        security_confidence=security_confidence,
        change_risk=change_risk,
        change_risk_confidence=change_risk_confidence,
        validation_focus=validation_focus,
        validation_focus_confidence=validation_focus_confidence,
    )
