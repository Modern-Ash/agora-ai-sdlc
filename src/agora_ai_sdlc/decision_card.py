"""Transparent confirmation card for the Agora Flow continuous wizard."""

from __future__ import annotations

from dataclasses import dataclass

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.workflow_advisor import WorkflowAdvice


@dataclass(frozen=True)
class DecisionCard:
    title: str
    rationale: tuple[str, ...]
    will_do: tuple[str, ...]
    will_not_do: tuple[str, ...]
    executor: str | None
    intelligence: str
    context_summary: str | None
    risk_summary: tuple[str, ...]
    validation_focus: str | None
    return_boundary: str


def build_decision_card(decision: GuidedDecision, advice: WorkflowAdvice) -> DecisionCard:
    rationale: list[str] = []
    if decision.missing_artifacts:
        rationale.append("Required artifacts are still missing: " + ", ".join(decision.missing_artifacts))
    if decision.unsatisfied_criteria:
        rationale.append("Acceptance criteria still need work: " + ", ".join(decision.unsatisfied_criteria))
    if decision.missing_evidence:
        rationale.append("Verification evidence is still missing: " + ", ".join(decision.missing_evidence))
    if getattr(advice, "escalation_required", False):
        rationale.append("Local System-1 confidence is below the configured threshold; generative reasoning is retained.")
    elif advice.source == "laya" and getattr(advice, "reasoning_tier", None):
        rationale.append(
            f"Local System-1 classified the reasoning tier as {advice.reasoning_tier}"
            + (f" with confidence {advice.confidence:.2f}." if getattr(advice, "confidence", None) is not None else ".")
        )
    if not rationale:
        rationale.append("Agora Core reports this as the next governed action.")

    if advice.action == "prepare":
        will_do = (
            "Assemble bounded context from authoritative Work/repository facts.",
            "Execute one governed, non-authoritative preparation iteration.",
            "Persist produced artifacts/evidence according to AI-DLC contracts.",
            "Re-read Agora Core immediately and recalculate the next step.",
        )
    elif advice.action == "verify":
        will_do = (
            "Run the allowlisted deterministic verification for this Work.",
            "Persist verification evidence.",
            "Re-read Agora Core and recalculate the next node.",
        )
    elif advice.action == "approve":
        will_do = (
            "Record only the explicit human approval shown on this card.",
            "Re-read Agora Core before attempting any lifecycle transition.",
        )
    elif advice.action == "transition":
        will_do = (
            "Apply the Core-authorized transition to the displayed target state.",
            "Continue immediately from the new workflow node.",
        )
    else:
        will_do = (
            "Present the evidence and outstanding obligations.",
            "Remain at the current human validation checkpoint.",
        )

    will_not_do = (
        "No human approval will be invented or recorded implicitly.",
        "No gate will be bypassed.",
        "No merge or production deployment will be performed implicitly.",
        "No unrelated repository context will be added by Laya.",
    )

    runtime = advice.recommended_runtime.label if advice.recommended_runtime is not None else None
    intelligence = "deterministic/Core"
    if advice.source == "laya":
        intelligence = "Laya local System-1"
        if getattr(advice, "reasoning_tier", None):
            intelligence += f" → {advice.reasoning_tier}"

    context_summary = None
    if getattr(advice, "context_candidates", 0):
        context_summary = (
            f"{advice.context_candidates} candidate files → {getattr(advice, 'context_selected', 0)} selected; "
            f"~{getattr(advice, 'context_tokens_before', 0)} → ~{getattr(advice, 'context_tokens_after', 0)} tokens "
            f"(~{getattr(advice, 'context_tokens_saved', 0)} avoided)"
        )

    risks = []
    if getattr(advice, "change_risk", None):
        confidence = getattr(advice, "change_risk_confidence", None)
        suffix = f" ({confidence:.2f})" if confidence is not None else ""
        risks.append(f"Change risk: {advice.change_risk}{suffix}.")
    if getattr(advice, "security_review", None) == "required":
        risks.append("Focused security review recommended by the local decision layer.")
    if getattr(advice, "context_escalated", ()):
        risks.append(f"{len(advice.context_escalated)} uncertain context item(s) retained fail-open.")
    if getattr(advice, "escalation_required", False):
        risks.append("Reasoning decision escalated because confidence was insufficient.")

    if advice.action in {"prepare", "verify", "approve", "transition"}:
        boundary = "Return immediately to the wizard after Core re-inspection."
    else:
        boundary = "Human validation is required before lifecycle progression."
    return DecisionCard(
        title=advice.summary,
        rationale=tuple(rationale),
        will_do=will_do,
        will_not_do=will_not_do,
        executor=runtime,
        intelligence=intelligence,
        context_summary=context_summary,
        risk_summary=tuple(risks),
        validation_focus=getattr(advice, "validation_focus", None),
        return_boundary=boundary,
    )


def render_decision_card(card: DecisionCard, *, lang: str = "en") -> str:
    es = lang == "es"
    labels = {
        "title": "Decisión propuesta" if es else "Proposed decision",
        "why": "Por qué" if es else "Why",
        "do": "Si confirmás, Agora hará" if es else "If confirmed, Agora will",
        "not": "Límites" if es else "Boundaries",
        "executor": "Executor",
        "intelligence": "Inteligencia" if es else "Intelligence",
        "context": "Contexto" if es else "Context",
        "risk": "Atención" if es else "Attention",
        "focus": "Foco de validación" if es else "Validation focus",
        "return": "Próximo checkpoint" if es else "Next checkpoint",
    }
    lines = [
        "╭─ " + labels["title"],
        "│ " + card.title,
        "│",
        "│ " + labels["why"],
        *[f"│   • {item}" for item in card.rationale],
        "│",
        "│ " + labels["do"],
        *[f"│   {index}. {item}" for index, item in enumerate(card.will_do, start=1)],
    ]
    if card.executor:
        lines.append(f"│ {labels['executor']}: {card.executor}")
    lines.append(f"│ {labels['intelligence']}: {card.intelligence}")
    if card.context_summary:
        lines.append(f"│ {labels['context']}: {card.context_summary}")
    if card.validation_focus:
        lines.append(f"│ {labels['focus']}: {card.validation_focus}")
    if card.risk_summary:
        lines.extend(["│", "│ " + labels["risk"], *[f"│   ! {item}" for item in card.risk_summary]])
    lines.extend(
        [
            "│",
            "│ " + labels["not"],
            *[f"│   • {item}" for item in card.will_not_do],
            "│",
            f"│ {labels['return']}: {card.return_boundary}",
            "╰" + "─" * 72,
        ]
    )
    return "\n".join(lines)
