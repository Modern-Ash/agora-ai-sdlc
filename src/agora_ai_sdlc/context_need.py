"""Top-level Decision Plane gate for repository artifact context."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from agora_ai_sdlc.decision_plane import (
    ConfidencePolicy,
    DecisionProvider,
    DecisionQuestion,
    evaluate_with_confidence,
)

SCHEMA = "context-need/v1"

CONTEXT_NEEDED_QUESTION = DecisionQuestion(
    id="context_needed",
    type="choice",
    instructions=(
        "Decide whether the next bounded generative action needs repository artifact context. "
        "Choose none only when the action can be completed safely without reading repository artifacts."
    ),
    criteria={
        "none": "repository artifact context is not needed for this bounded action",
        "bounded": "use the deterministic Context Graph and relevance pruning to select bounded repository context",
    },
)


@dataclass(frozen=True)
class ContextNeedDecision:
    value: str
    confidence: float
    source: str
    escalated: bool
    latency_ms: float = 0.0
    cache_key: str | None = None
    reused: bool = False


@dataclass
class ContextNeedCache:
    values: dict[str, ContextNeedDecision] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0


def deterministic_context_need(action: str | None) -> ContextNeedDecision | None:
    """Resolve only actions that provably do not need repository artifact context."""

    no_context_actions = {
        "human-approval",
        "governed-transition",
        "advance-criterion",
        "mark-deployed",
        "accept-criteria",
        "submit-pr",
        "publish-local-artifacts",
    }
    if action in no_context_actions:
        return ContextNeedDecision("none", 1.0, "system0", False)
    return None


def _cache_key(
    *,
    action: str | None,
    objective: str | None,
    acceptance_criteria: tuple[str, ...],
    provider: DecisionProvider,
) -> str:
    payload = {
        "schema": SCHEMA,
        "action": action,
        "objective": objective or "",
        "acceptance_criteria": list(acceptance_criteria),
        "provider": getattr(provider, "name", type(provider).__name__),
        "model": getattr(provider, "model", None),
        "question": CONTEXT_NEEDED_QUESTION.as_laya(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def decide_context_need(
    *,
    action: str | None,
    objective: str | None,
    acceptance_criteria: tuple[str, ...],
    provider: DecisionProvider,
    confidence_threshold: float = 0.90,
    cache: ContextNeedCache | None = None,
) -> ContextNeedDecision:
    """Decide context need; uncertainty fails open to bounded Context Graph selection."""

    deterministic = deterministic_context_need(action)
    if deterministic is not None:
        return deterministic

    store = cache or ContextNeedCache()
    key = _cache_key(
        action=action,
        objective=objective,
        acceptance_criteria=acceptance_criteria,
        provider=provider,
    )
    cached = store.values.get(key)
    if cached is not None:
        store.hits += 1
        return ContextNeedDecision(
            cached.value,
            cached.confidence,
            cached.source,
            cached.escalated,
            latency_ms=0.0,
            cache_key=key,
            reused=True,
        )
    store.misses += 1

    state = {
        "action": action or "",
        "objective": objective or "",
        "acceptance_criteria": list(acceptance_criteria),
    }
    evaluated = evaluate_with_confidence(
        provider,
        state,
        (CONTEXT_NEEDED_QUESTION,),
        policy=ConfidencePolicy(confidence_threshold),
    )
    answer = evaluated.result.answers["context_needed"]
    escalated = bool(evaluated.escalated)
    decision = ContextNeedDecision(
        value="bounded" if escalated else str(answer.value),
        confidence=float(answer.confidence),
        source="laya",
        escalated=escalated,
        latency_ms=evaluated.result.latency_ms or 0.0,
        cache_key=key,
    )
    store.values[key] = decision
    return decision
