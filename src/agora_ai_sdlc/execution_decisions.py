"""Decision state adapters for deterministic execution bundles."""

from __future__ import annotations

from typing import Any

from agora_ai_sdlc.decision_plane import (
    ConfidencePolicy,
    DecisionAnswer,
    DecisionEvaluation,
    DecisionPlaneError,
    DecisionProvider,
    DecisionQuestion,
    DecisionResult,
    evaluate_with_confidence,
)
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.system0_decisions import resolve_system0, threshold_for

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
    confidence_thresholds: dict[str, float] | None = None,
) -> DecisionEvaluation:
    """Return System-0 + advisory Laya signals without mutating authority."""

    state = execution_state(bundle)
    system0 = resolve_system0(bundle)
    questions = tuple(question for question in BASE_EXECUTION_QUESTIONS if question.id not in system0)
    joint_planner = bool(
        "planner_needed" not in system0 and getattr(provider, "supports_joint_execution_questions", False)
    )
    if joint_planner:
        questions = (*questions, PLANNER_QUESTION)

    answers = {}
    accepted = []
    escalated = []
    provider_name = getattr(provider, "name", type(provider).__name__)
    model = getattr(provider, "model", None)
    latency = 0.0
    metadata = {"system0": {name: answer.reason for name, answer in sorted(system0.items())}}

    if questions:
        # Keep one provider call for the unresolved base questions. Confidence
        # remains risk-calibrated per answer after the shared inference pass.
        result = provider.decide(state, questions)
        expected = {question.id for question in questions}
        if set(result.answers) != expected:
            raise DecisionPlaneError(
                "decision.answer_set",
                f"provider answer set mismatch; expected={sorted(expected)!r} actual={sorted(result.answers)!r}",
            )
        provider_name = result.provider
        model = result.model
        latency += result.latency_ms or 0.0
        metadata.update(result.metadata)
        for question in questions:
            answer = result.answers[question.id]
            answers[question.id] = answer
            threshold = (
                confidence_threshold
                if confidence_thresholds is None
                else threshold_for(question.id, confidence_thresholds)
            )
            (accepted if answer.confidence >= threshold else escalated).append(question.id)

    for name, resolved in system0.items():
        question = next(
            (item for item in (*BASE_EXECUTION_QUESTIONS, PLANNER_QUESTION) if item.id == name),
            None,
        )
        if question is None:
            continue
        answers[name] = DecisionAnswer(name, question.type, resolved.value, 1.0)
        accepted.append(name)

    metadata["provider_calls"] = 1 if questions else 0
    metadata["planner_batched"] = joint_planner

    if "planner_needed" not in system0 and not joint_planner:
        try:
            planner_threshold = (
                confidence_threshold
                if confidence_thresholds is None
                else threshold_for("planner_needed", confidence_thresholds)
            )
            planner = evaluate_with_confidence(
                provider,
                state,
                (PLANNER_QUESTION,),
                policy=ConfidencePolicy(planner_threshold),
            )
            answers.update(planner.result.answers)
            accepted.extend(planner.accepted)
            escalated.extend(planner.escalated)
            provider_name = planner.result.provider
            model = planner.result.model
            latency += planner.result.latency_ms or 0.0
            metadata.update(planner.result.metadata)
            metadata["provider_calls"] += 1
        except Exception as error:  # noqa: BLE001 - optional advisory compatibility boundary
            metadata["planner_advisory_error"] = type(error).__name__

    result = DecisionResult(
        provider=provider_name,
        model=model,
        answers=answers,
        latency_ms=latency,
        metadata=metadata,
    )
    return DecisionEvaluation(
        result=result,
        accepted=tuple(dict.fromkeys(accepted)),
        escalated=tuple(dict.fromkeys(escalated)),
    )
