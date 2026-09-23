"""Proactive workflow advice for the guided AI-SDLC experience.

Laya is used as a local, cheap classifier below the UX. Agora Core remains the
source of truth and all authority-bearing steps remain explicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.executor_recovery import ExecutorRecoveryChoice, recovery_choices
from agora_ai_sdlc.execution_bundle import build_execution_bundle
from agora_ai_sdlc.execution_decisions import advise_execution
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.laya_provider import LayaDecisionProvider, LayaUnavailable


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
    """Choose the simplest next interaction and use Laya only where it adds value."""

    # Authority-bearing decisions never go through Laya.
    if decision.ready_for_human_approval and decision.missing_approvals:
        return WorkflowAdvice(
            action="review",
            summary="Review the completed evidence and make the required human approval decision.",
            needs_runtime=False,
        )

    # Verification is deterministic and cheaper than any model call.
    if decision.missing_evidence and not (
        decision.missing_artifacts or decision.clarification_issues or decision.unsatisfied_criteria
    ):
        return WorkflowAdvice(
            action="review",
            summary="Run or inspect deterministic verification before spending tokens on another agent.",
            needs_runtime=False,
        )

    needs_preparation = bool(
        decision.missing_artifacts
        or decision.clarification_issues
        or decision.unsatisfied_criteria
        or decision.blocked
    )
    if not needs_preparation:
        return WorkflowAdvice(
            action="review",
            summary="The governed step is ready for the responsible actor; review before the transition.",
            needs_runtime=False,
        )

    tier = None
    confidence = None
    source = "deterministic"
    escalation = False
    try:
        bundle = build_execution_bundle(
            root,
            swarm=decision.swarm,
            work=decision.work,
            persist=False,
        )
        evaluated = advise_execution(
            bundle,
            provider=LayaDecisionProvider(),
            confidence_threshold=confidence_threshold,
        )
        answer = evaluated.result.answers.get("reasoning_tier")
        if answer is not None:
            tier = str(answer.value)
            confidence = answer.confidence
            source = "laya"
            escalation = "reasoning_tier" in evaluated.escalated
    except (LayaUnavailable, OSError, RuntimeError, ValueError):
        pass

    recommended = None
    # Token-saving default: automatically preselect only local/free executors.
    # Paid/configured providers still require the user's explicit runtime choice.
    if tier in {None, "local", "standard"} and not escalation:
        recommended = _free_runtime(root)

    if tier == "human" and not escalation:
        return WorkflowAdvice(
            action="review",
            summary="The next step needs human judgement rather than another generative call.",
            needs_runtime=False,
            reasoning_tier=tier,
            confidence=confidence,
            source=source,
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
    )
