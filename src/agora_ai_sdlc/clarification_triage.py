"""Laya triage for deterministic Inception clarification gaps."""

from __future__ import annotations

from dataclasses import dataclass

from agora_ai_sdlc.decision_plane import (
    ConfidencePolicy,
    DecisionProvider,
    DecisionQuestion,
    evaluate_with_confidence,
)
from agora_ai_sdlc.deterministic_inception import IssueFacts

GAP_QUESTION = DecisionQuestion(
    id="material_gap",
    type="choice",
    instructions=(
        "Decide whether this candidate clarification is a material ambiguity that blocks safe Inception. "
        "Do not invent missing requirements; classify only the explicit candidate gap against the issue facts."
    ),
    criteria={
        "none": "the issue facts already resolve the candidate gap sufficiently for bounded delivery planning",
        "expected-behavior": "observable expected behavior remains materially ambiguous",
        "acceptance-criteria": "success/failure acceptance criteria remain materially ambiguous",
        "security": "a security, permission, credential or trust-boundary decision is missing",
        "persistence": "data ownership, storage, migration or persistence behavior is materially ambiguous",
        "integration": "an external-system or interface contract is materially ambiguous",
        "operations": "deployment, rollback or operational behavior is materially ambiguous",
        "constraints": "explicit requirements or constraints conflict materially",
        "business-decision": "a product/actor/business decision requires human authority",
    },
)


@dataclass(frozen=True)
class ClarificationGap:
    source: str
    category: str
    confidence: float
    escalated: bool


@dataclass(frozen=True)
class ClarificationTriage:
    gaps: tuple[ClarificationGap, ...]
    provider: str | None
    model: str | None
    latency_ms: float

    @property
    def material_gaps(self) -> tuple[ClarificationGap, ...]:
        return tuple(gap for gap in self.gaps if gap.category != "none")

    @property
    def unresolved(self) -> tuple[ClarificationGap, ...]:
        return tuple(gap for gap in self.gaps if gap.escalated)


def triage_clarifications(
    issue: IssueFacts,
    candidate_gaps: tuple[str, ...],
    *,
    provider: DecisionProvider,
    confidence_threshold: float = 0.90,
) -> ClarificationTriage:
    """Classify only deterministic candidate gaps; low confidence fails open."""

    if not candidate_gaps:
        return ClarificationTriage((), None, None, 0.0)

    states = tuple(
        {
            "objective": issue.objective,
            "requirements": list(issue.requirements),
            "acceptance_criteria": list(issue.acceptance_criteria),
            "dependencies": list(issue.dependencies),
            "constraints": list(issue.constraints),
            "candidate_gap": gap,
        }
        for gap in candidate_gaps
    )

    batch = getattr(provider, "decide_many", None)
    evaluations = []
    if callable(batch):
        results = batch(tuple((state, (GAP_QUESTION,)) for state in states))
        if len(results) != len(states):
            raise ValueError("decision provider returned an unexpected clarification batch size")
        for result in results:
            answer = result.answers.get("material_gap")
            if answer is None:
                raise ValueError("decision provider omitted material_gap answer")
            evaluations.append((result, answer, answer.confidence < confidence_threshold))
    else:
        for state in states:
            evaluation = evaluate_with_confidence(
                provider,
                state,
                (GAP_QUESTION,),
                policy=ConfidencePolicy(confidence_threshold),
            )
            answer = evaluation.result.answers["material_gap"]
            evaluations.append((evaluation.result, answer, bool(evaluation.escalated)))

    gaps = tuple(
        ClarificationGap(
            source=source,
            category=str(answer.value),
            confidence=float(answer.confidence),
            escalated=escalated,
        )
        for source, (_, answer, escalated) in zip(candidate_gaps, evaluations)
    )
    provider_name = evaluations[0][0].provider if evaluations else None
    model = evaluations[0][0].model if evaluations else None
    latency = sum(result.latency_ms or 0.0 for result, _, _ in evaluations)
    return ClarificationTriage(gaps, provider_name, model, latency)
