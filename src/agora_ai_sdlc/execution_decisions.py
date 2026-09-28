"""Decision state adapters for deterministic execution bundles."""

from __future__ import annotations

from typing import Any

from agora_ai_sdlc.decision_plane import (
    ConfidencePolicy,
    DecisionEvaluation,
    DecisionProvider,
    DecisionQuestion,
    DecisionResult,
    evaluate_with_confidence,
)
from agora_ai_sdlc.execution_bundle import ExecutionBundle

BASE_EXECUTION_QUESTIONS = (
    DecisionQuestion(
        id="reasoning_tier",
        type="choice",
        instructions="Choose the minimum reasoning tier needed for the next implementation or review action.",
        criteria={
            "local": "bounded change with clear acceptance criteria and mechanical verification",
            "standard": "moderate reasoning or cross-file implementation work",
            "frontier": "architectural ambiguity, novel design trade-offs or high-risk reasoning",
            "human": "business judgement or explicit human authority is required",
        },
    ),
    DecisionQuestion(
        id="security_review",
        type="choice",
        instructions="Does the observed change need focused security review beyond normal verification?",
        criteria={
            "required": "security-sensitive behavior, permissions, credentials, authentication or trust boundary is affected",
            "normal": "normal verification is sufficient based on the observed change",
        },
    ),
    DecisionQuestion(
        id="change_risk",
        type="choice",
        instructions="Classify the implementation risk for the next bounded change.",
        criteria={
            "low": "localized change with clear acceptance criteria, existing patterns and direct verification",
            "moderate": "cross-file or integration change with manageable trade-offs and verification",
            "high": "architectural, data, security, infrastructure or irreversible change with material uncertainty",
        },
    ),
    DecisionQuestion(
        id="validation_focus",
        type="choice",
        instructions="Choose the primary validation focus that should be highlighted to the developer.",
        criteria={
            "functional": "correct behavior and acceptance criteria are the primary concern",
            "security": "trust, permissions, authentication, secrets or attack surface are primary",
            "performance": "latency, throughput, scaling or resource use are primary",
            "architecture": "coupling, boundaries, integration contracts or structural design are primary",
            "operations": "deployment, rollback, observability or production readiness are primary",
        },
    ),
)

PLANNER_QUESTION = DecisionQuestion(
    id="planner_needed",
    type="choice",
    instructions=(
        "Choose the minimum planning assistance needed before the next bounded execution. "
        "Prefer none or template when acceptance criteria and verification make the work mechanically actionable."
    ),
    criteria={
        "none": "the next action is already explicit and needs no separate planning pass",
        "template": "a deterministic phase template is sufficient to guide execution",
        "local": "a local or free planner may help structure bounded implementation work",
        "generative": "moderate ambiguity or cross-file coordination justifies a paid-efficient planner",
        "frontier": "architectural ambiguity, high risk or material design trade-offs require frontier planning",
    },
)

# Backward-compatible public question set. Planner need is an optional,
# separately evaluated advisory dimension so existing DecisionProviders remain valid.
EXECUTION_QUESTIONS = BASE_EXECUTION_QUESTIONS


def execution_state(bundle: ExecutionBundle) -> dict[str, Any]:
    """Project a deterministic bundle into compact, provider-neutral decision state."""

    return {
        "stage": bundle.stage,
        "next_action": bundle.next_action,
        "objective": bundle.objective,
        "acceptance_criteria": list(bundle.acceptance_criteria),
        "changed_paths": list(bundle.changed_paths),
        "dirty_paths": list(bundle.dirty_paths),
        "related_paths": list(bundle.related_paths),
        "languages": list(bundle.languages),
        "build_systems": list(bundle.build_systems),
        "risks": list(bundle.risks),
        "governance": {
            "human_approval_required": bundle.governance.get("human_approval_required", False),
            "missing_artifacts": list(bundle.governance.get("missing_artifacts", ())),
            "missing_evidence": list(bundle.governance.get("missing_evidence", ())),
            "missing_approvals": list(bundle.governance.get("missing_approvals", ())),
            "unsatisfied_criteria": list(bundle.governance.get("unsatisfied_criteria", ())),
            "ready_to_transition": bundle.governance.get("ready_to_transition", False),
        },
    }


def advise_execution(
    bundle: ExecutionBundle,
    *,
    provider: DecisionProvider,
    confidence_threshold: float = 0.90,
) -> DecisionEvaluation:
    """Return advisory Laya signals. Never mutate or authorize the bundle."""

    state = execution_state(bundle)
    base = evaluate_with_confidence(
        provider,
        state,
        BASE_EXECUTION_QUESTIONS,
        policy=ConfidencePolicy(confidence_threshold),
    )
    # Planner need is a new optional advisory dimension. Legacy/custom
    # DecisionProviders that implement the established execution questions
    # must continue to work; failure here means "no separate planner".
    try:
        planner = evaluate_with_confidence(
            provider,
            state,
            (PLANNER_QUESTION,),
            policy=ConfidencePolicy(confidence_threshold),
        )
    except Exception:  # noqa: BLE001 - optional advisory compatibility boundary
        return base

    answers = dict(base.result.answers)
    answers.update(planner.result.answers)
    result = DecisionResult(
        provider=base.result.provider,
        model=base.result.model,
        answers=answers,
        latency_ms=(base.result.latency_ms or 0.0) + (planner.result.latency_ms or 0.0),
        metadata=base.result.metadata,
    )
    return DecisionEvaluation(
        result=result,
        accepted=tuple(dict.fromkeys((*base.accepted, *planner.accepted))),
        escalated=tuple(dict.fromkeys((*base.escalated, *planner.escalated))),
    )
