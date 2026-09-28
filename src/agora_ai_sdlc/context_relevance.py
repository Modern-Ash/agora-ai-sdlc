"""Shared batched/cache-aware relevance classification for bounded context."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from agora_ai_sdlc.decision_plane import ConfidencePolicy, DecisionProvider, DecisionQuestion, evaluate_with_confidence

SCHEMA = "context-relevance/v1"


@dataclass(frozen=True)
class RelevanceInput:
    id: str
    state: dict[str, Any]
    content: str


@dataclass(frozen=True)
class RelevanceClassification:
    label: str
    confidence: float
    escalated: bool
    latency_ms: float
    cache_key: str
    reused: bool = False


@dataclass
class RelevanceCache:
    values: dict[str, RelevanceClassification] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0


def _digest(item: RelevanceInput, *, provider: DecisionProvider, question: DecisionQuestion) -> str:
    payload = {
        "schema": SCHEMA,
        "provider": getattr(provider, "name", type(provider).__name__),
        "model": getattr(provider, "model", None),
        "question": question.as_laya(),
        "state": item.state,
        "content_sha256": hashlib.sha256(item.content.encode()).hexdigest(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def classify_relevance(
    items: tuple[RelevanceInput, ...],
    *,
    provider: DecisionProvider,
    question: DecisionQuestion,
    confidence_threshold: float,
    cache: RelevanceCache | None = None,
) -> dict[str, RelevanceClassification]:
    """Classify cache misses in one batch when supported; uncertainty fails open upstream."""

    store = cache or RelevanceCache()
    output: dict[str, RelevanceClassification] = {}
    pending: list[tuple[RelevanceInput, str]] = []

    for item in items:
        key = _digest(item, provider=provider, question=question)
        cached = store.values.get(key)
        if cached is not None:
            store.hits += 1
            output[item.id] = RelevanceClassification(
                label=cached.label,
                confidence=cached.confidence,
                escalated=cached.escalated,
                latency_ms=0.0,
                cache_key=key,
                reused=True,
            )
        else:
            store.misses += 1
            pending.append((item, key))

    batch = getattr(provider, "decide_many", None)
    if pending and callable(batch):
        raw = batch(tuple((item.state, (question,)) for item, _ in pending))
        if len(raw) != len(pending):
            raise ValueError("decision provider returned an unexpected relevance batch size")
        evaluations = []
        for result in raw:
            answer = result.answers.get(question.id)
            if answer is None:
                raise ValueError("decision provider batch omitted relevance answer")
            evaluations.append((result, answer, answer.confidence < confidence_threshold))
    else:
        evaluations = []
        for item, _ in pending:
            evaluated = evaluate_with_confidence(
                provider,
                item.state,
                (question,),
                policy=ConfidencePolicy(confidence_threshold),
            )
            answer = evaluated.result.answers[question.id]
            evaluations.append((evaluated.result, answer, bool(evaluated.escalated)))

    for (item, key), (result, answer, escalated) in zip(pending, evaluations):
        value = RelevanceClassification(
            label=str(answer.value),
            confidence=float(answer.confidence),
            escalated=escalated,
            latency_ms=result.latency_ms or 0.0,
            cache_key=key,
        )
        store.values[key] = value
        output[item.id] = value

    return output
