"""Decision state adapters for deterministic execution bundles."""

from __future__ import annotations

from typing import Any

from agora_ai_sdlc.decision_plane import (
    ConfidencePolicy,
    DecisionEvaluation,
    DecisionProvider,
    DecisionQuestion,
    evaluate_with_confidence,
)
from agora_ai_sdlc.execution_bundle import ExecutionBundle

EXECUTION_QUESTIONS = (
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
)


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

    return evaluate_with_confidence(
        provider,
        execution_state(bundle),
        EXECUTION_QUESTIONS,
        policy=ConfidencePolicy(confidence_threshold),
    )
