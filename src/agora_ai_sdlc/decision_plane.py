"""Provider-neutral decision plane contracts.

The plane may recommend or classify. It never grants lifecycle authority:
Agora Core policies, evidence and human approvals remain authoritative.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

VALID_TYPES = {"choice", "score", "noul"}


class DecisionPlaneError(ValueError):
    """Stable decision-plane failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class DecisionQuestion:
    id: str
    type: str
    instructions: str
    criteria: Mapping[str, str] | tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise DecisionPlaneError("decision.question_id", "question id must not be empty")
        if self.type not in VALID_TYPES:
            raise DecisionPlaneError("decision.question_type", f"unsupported question type {self.type!r}")
        if not self.instructions.strip():
            raise DecisionPlaneError("decision.instructions", "instructions must not be empty")

    def as_laya(self) -> dict[str, Any]:
        criteria: Any = dict(self.criteria) if isinstance(self.criteria, Mapping) else list(self.criteria)
        return {
            "type": self.type,
            "instructions": self.instructions,
            "criteria": criteria,
        }


@dataclass(frozen=True)
class DecisionAnswer:
    question: str
    type: str
    value: str | float | bool
    confidence: float
    probabilities: Mapping[str, float] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise DecisionPlaneError("decision.confidence", "confidence must be between 0 and 1")


@dataclass(frozen=True)
class DecisionResult:
    provider: str
    answers: Mapping[str, DecisionAnswer]
    latency_ms: float | None = None
    model: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class DecisionProvider(Protocol):
    name: str

    def decide(
        self,
        state: Mapping[str, Any],
        questions: tuple[DecisionQuestion, ...],
    ) -> DecisionResult: ...


@dataclass(frozen=True)
class ConfidencePolicy:
    threshold: float = 0.90

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise DecisionPlaneError("decision.threshold", "threshold must be between 0 and 1")


@dataclass(frozen=True)
class DecisionEvaluation:
    result: DecisionResult
    accepted: tuple[str, ...]
    escalated: tuple[str, ...]

    @property
    def all_confident(self) -> bool:
        return not self.escalated


def evaluate_with_confidence(
    provider: DecisionProvider,
    state: Mapping[str, Any],
    questions: tuple[DecisionQuestion, ...],
    *,
    policy: ConfidencePolicy | None = None,
) -> DecisionEvaluation:
    """Evaluate advisory decisions and mark low-confidence answers for escalation.

    "accepted" means accepted as an advisory signal only. It does not authorize
    a lifecycle transition, gate approval, merge, deployment or human approval.
    """

    chosen = policy or ConfidencePolicy()
    result = provider.decide(state, questions)
    expected = {question.id for question in questions}
    actual = set(result.answers)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise DecisionPlaneError(
            "decision.answer_set",
            f"provider answer set mismatch; missing={missing!r} extra={extra!r}",
        )
    accepted = tuple(q.id for q in questions if result.answers[q.id].confidence >= chosen.threshold)
    escalated = tuple(q.id for q in questions if q.id not in accepted)
    return DecisionEvaluation(result=result, accepted=accepted, escalated=escalated)


EXECUTION_TIER_QUESTION = DecisionQuestion(
    id="execution_tier",
    type="choice",
    instructions=(
        "Choose the least expensive execution tier that can safely complete the work. "
        "Use human only when authority or business judgement is required."
    ),
    criteria={
        "local": "simple, bounded or mechanically verifiable work suitable for a local model",
        "standard": "work needing moderate generative reasoning",
        "frontier": "ambiguous, architectural or high-reasoning work",
        "human": "decision requires explicit human authority or business judgement",
    },
)
