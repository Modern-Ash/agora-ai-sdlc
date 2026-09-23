"""Deterministic clarification materialization for explicit zero-gap Inception."""

from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass

from agora.model import WorkActorInput


@dataclass(frozen=True)
class DeterministicClarificationResult:
    actions: tuple[str, ...]


def _zero_question_runner() -> str:
    return shlex.join(
        [
            sys.executable,
            "-m",
            "agora_ai_sdlc.deterministic_advisor",
            "zero-clarification",
        ]
    )


def record_zero_question_clarification(
    *,
    workspace,
    swarm_id: str,
    work_id: str,
    actor_id: str,
) -> DeterministicClarificationResult:
    """Record a current zero-question Core clarification without invoking an LLM."""

    if not actor_id:
        raise ValueError("deterministic clarification requires the assigned developer actor")

    result = workspace.clarify_work(
        WorkActorInput(
            swarm_id=swarm_id,
            work_id=work_id,
            actor_id=actor_id,
        ),
        runner=_zero_question_runner(),
    )
    questions = result.get("questions") if isinstance(result, dict) else None
    if questions != []:
        raise ValueError("deterministic zero-question clarification returned unexpected questions")
    return DeterministicClarificationResult(
        actions=("clarification.resolved:deterministic-zero-question",)
    )
