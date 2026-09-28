"""System-0 advisory floors and per-question confidence policy.

These rules only pre-resolve facts that are explicit in the deterministic
execution bundle. They never grant authority and Laya may tighten, never weaken,
a deterministic floor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agora_ai_sdlc.execution_bundle import ExecutionBundle

DEFAULT_THRESHOLDS = {
    "reasoning_tier": 0.90,
    "security_review": 0.95,
    "change_risk": 0.90,
    "validation_focus": 0.80,
    "planner_needed": 0.90,
}


@dataclass(frozen=True)
class System0Answer:
    value: str
    reason: str


def resolve_system0(bundle: ExecutionBundle) -> dict[str, System0Answer]:
    """Resolve only unambiguous advisory facts from the deterministic bundle."""

    answers: dict[str, System0Answer] = {}
    governance = bundle.governance

    if bundle.next_action == "human-approval" or governance.get("human_approval_required"):
        answers["reasoning_tier"] = System0Answer("human", "explicit-human-authority-boundary")
        answers["planner_needed"] = System0Answer("none", "human-authority-does-not-use-ai-planner")

    risk_text = " ".join(str(item).casefold() for item in bundle.risks)
    security_markers = (
        "security",
        "authentication",
        "authorization",
        "credential",
        "secret",
        "permission",
        "trust boundary",
    )
    if any(marker in risk_text for marker in security_markers):
        answers["security_review"] = System0Answer("required", "explicit-security-risk")
        answers["change_risk"] = System0Answer("moderate", "explicit-security-risk-floor")
        answers["validation_focus"] = System0Answer("security", "explicit-security-risk")

    if bundle.stage == "operations" and (
        governance.get("missing_evidence") or governance.get("missing_artifacts")
    ):
        answers.setdefault(
            "validation_focus",
            System0Answer("operations", "operations-stage-readiness-gap"),
        )

    return answers


def threshold_for(question: str, overrides: dict[str, float] | None = None) -> float:
    values: dict[str, Any] = {**DEFAULT_THRESHOLDS, **(overrides or {})}
    value = float(values.get(question, 0.90))
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"invalid confidence threshold for {question!r}: {value}")
    return value
