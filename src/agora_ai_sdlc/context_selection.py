"""Laya-assisted semantic pruning over deterministic Agora context candidates.

The deterministic context graph defines the candidate set. Laya may only reduce
that set; it cannot add unrelated artifacts or grant lifecycle authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from agora_ai_sdlc.context_graph import ContextBundle, Graph, context_bundle
from agora_ai_sdlc.decision_metrics import DecisionMetrics
from agora_ai_sdlc.decision_plane import (
    ConfidencePolicy,
    DecisionProvider,
    DecisionQuestion,
    evaluate_with_confidence,
)

RELEVANCE_QUESTION = DecisionQuestion(
    id="relevance",
    type="choice",
    instructions=(
        "Classify how necessary this candidate artifact is for completing the current software-delivery task. "
        "Prefer irrelevant when the artifact does not materially affect implementation, verification or governance."
    ),
    criteria={
        "required": "must be read to implement or verify the current task safely",
        "useful": "contains supporting context likely to improve the implementation",
        "irrelevant": "not needed for this task",
    },
)


@dataclass(frozen=True)
class ContextSelection:
    candidate: ContextBundle
    selected: ContextBundle
    classifications: Mapping[str, str]
    confidences: Mapping[str, float]
    escalated: tuple[str, ...]
    metrics: DecisionMetrics

    def snapshot(self) -> dict:
        return {
            "candidate": self.candidate.snapshot(),
            "selected": self.selected.snapshot(),
            "classifications": dict(self.classifications),
            "confidences": dict(self.confidences),
            "escalated": list(self.escalated),
            "metrics": self.metrics.snapshot(),
        }


def _bounded_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head
    return text[:head] + "\n...[bounded for Laya relevance decision]...\n" + text[-tail:]


def _filtered_bundle(source: ContextBundle, keep: set[str]) -> ContextBundle:
    items = tuple(item for item in source.items if item.id in keep)
    text = {item.id: source.text[item.id] for item in items}
    return ContextBundle(
        root=source.root,
        direction=source.direction,
        items=items,
        omitted=tuple(dict.fromkeys((*source.omitted, *(item.id for item in source.items if item.id not in keep)))),
        dangling=source.dangling,
        cycles=source.cycles,
        total_tokens=sum(item.tokens for item in items),
        text=text,
    )


def select_context_with_laya(
    graph: Graph,
    root: str,
    *,
    provider: DecisionProvider,
    objective: str | None = None,
    acceptance_criteria: tuple[str, ...] = (),
    direction: str = "both",
    max_depth: int | None = None,
    max_tokens: int | None = None,
    confidence_threshold: float = 0.90,
    keep_useful: bool = True,
    artifact_max_chars: int = 2800,
) -> ContextSelection:
    """Prune a deterministic candidate bundle with local Laya relevance decisions.

    Low-confidence classifications fail open: the artifact is retained for the
    generative executor instead of being silently discarded.
    """

    candidate = context_bundle(
        graph,
        root,
        direction=direction,
        max_depth=max_depth,
        max_tokens=None,
    )
    keep = {root}
    classifications: dict[str, str] = {root: "required"}
    confidences: dict[str, float] = {root: 1.0}
    escalated: list[str] = []
    metrics = DecisionMetrics(candidate_context_tokens=candidate.total_tokens)

    for item in candidate.items:
        if item.id == root:
            continue
        state = {
            "objective": objective or "",
            "acceptance_criteria": list(acceptance_criteria),
            "root_artifact": root,
            "candidate": {
                "id": item.id,
                "kind": item.kind,
                "relation": item.relation,
                "distance": item.distance,
                "path": item.path,
                "content": _bounded_text(candidate.text[item.id], artifact_max_chars),
            },
        }
        evaluation = evaluate_with_confidence(
            provider,
            state,
            (RELEVANCE_QUESTION,),
            policy=ConfidencePolicy(confidence_threshold),
        )
        answer = evaluation.result.answers["relevance"]
        label = str(answer.value)
        classifications[item.id] = label
        confidences[item.id] = answer.confidence
        metrics.decisions += 1
        metrics.laya_latency_ms += evaluation.result.latency_ms or 0.0

        if evaluation.escalated:
            # Fail open: preserve context when System-1 is uncertain.
            keep.add(item.id)
            escalated.append(item.id)
            metrics.escalated += 1
            continue

        metrics.confident += 1
        metrics.avoided_llm_calls += 1
        if label == "required" or (keep_useful and label == "useful"):
            keep.add(item.id)

    selected = _filtered_bundle(candidate, keep)

    # Enforce the final generative token budget after semantic pruning.
    if max_tokens is not None and selected.total_tokens > max_tokens:
        allowed = {root}
        running = next(item.tokens for item in selected.items if item.id == root)
        for item in selected.items:
            if item.id == root:
                continue
            if running + item.tokens <= max_tokens:
                allowed.add(item.id)
                running += item.tokens
        selected = _filtered_bundle(selected, allowed)

    metrics.selected_context_tokens = selected.total_tokens
    return ContextSelection(
        candidate=candidate,
        selected=selected,
        classifications=classifications,
        confidences=confidences,
        escalated=tuple(escalated),
        metrics=metrics,
    )
