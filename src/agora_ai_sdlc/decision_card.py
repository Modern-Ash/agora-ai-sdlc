"""Transparent confirmation card for the Agora Flow continuous wizard."""

from __future__ import annotations

from dataclasses import dataclass

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.i18n import t
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


def _localized_value(kind: str, value: str | None, *, lang: str) -> str | None:
    if value is None:
        return None
    key = f"decision.value.{kind}.{value}"
    translated = t(key, lang=lang)
    return value if translated == key else translated


def build_decision_card(
    decision: GuidedDecision,
    advice: WorkflowAdvice,
    *,
    lang: str = "en",
) -> DecisionCard:
    rationale: list[str] = []
    if decision.missing_artifacts:
        rationale.append(t("decision.reason.missing_artifacts", lang=lang, items=", ".join(decision.missing_artifacts)))
    if decision.unsatisfied_criteria:
        rationale.append(t("decision.reason.criteria", lang=lang, items=", ".join(decision.unsatisfied_criteria)))
    if decision.missing_evidence:
        rationale.append(t("decision.reason.evidence", lang=lang, items=", ".join(decision.missing_evidence)))
    if getattr(advice, "escalation_required", False):
        rationale.append(t("decision.reason.low_confidence", lang=lang))
    elif advice.source == "laya" and getattr(advice, "reasoning_tier", None):
        tier = _localized_value("tier", advice.reasoning_tier, lang=lang) or advice.reasoning_tier
        if getattr(advice, "confidence", None) is not None:
            rationale.append(
                t(
                    "decision.reason.laya_tier_confidence",
                    lang=lang,
                    tier=tier,
                    confidence=f"{advice.confidence:.2f}",
                )
            )
        else:
            rationale.append(t("decision.reason.laya_tier", lang=lang, tier=tier))
    if not rationale:
        rationale.append(t("decision.reason.core_next", lang=lang))

    actions = {
        "prepare": (
            "decision.do.prepare.context",
            "decision.do.prepare.execute",
            "decision.do.prepare.persist",
            "decision.do.prepare.reinspect",
        ),
        "verify": (
            "decision.do.verify.run",
            "decision.do.verify.persist",
            "decision.do.verify.reinspect",
        ),
        "advance-criterion": (
            "decision.do.advance_criterion.record",
            "decision.do.advance_criterion.reinspect",
        ),
        "submit-pr": (
            "decision.do.submit_pr.changes",
            "decision.do.submit_pr.commit",
            "decision.do.submit_pr.push",
            "decision.do.submit_pr.create",
            "decision.do.submit_pr.evidence",
        ),
        "approve": (
            "decision.do.approve.record",
            "decision.do.approve.reinspect",
        ),
        "accept-criteria": (
            "decision.do.accept_criteria.record",
            "decision.do.accept_criteria.reinspect",
        ),
        "mark-deployed": (
            "decision.do.mark_deployed.record",
            "decision.do.mark_deployed.reinspect",
        ),
        "transition": (
            "decision.do.transition.apply",
            "decision.do.transition.continue",
        ),
        "review": (
            "decision.do.review.present",
            "decision.do.review.remain",
        ),
    }
    will_do = tuple(t(key, lang=lang) for key in actions.get(advice.action, actions["review"]))

    will_not_do = (
        t("decision.boundary.no_implicit_approval", lang=lang),
        t("decision.boundary.no_gate_bypass", lang=lang),
        t("decision.boundary.no_merge_deploy", lang=lang),
        t("decision.boundary.no_unrelated_context", lang=lang),
    )

    runtime = advice.recommended_runtime.label if advice.recommended_runtime is not None else None
    intelligence = t("decision.intelligence.deterministic", lang=lang)
    if advice.source == "laya":
        intelligence = t("decision.intelligence.laya", lang=lang)
        if getattr(advice, "reasoning_tier", None):
            tier = _localized_value("tier", advice.reasoning_tier, lang=lang) or advice.reasoning_tier
            intelligence += f" → {tier}"

    context_summary = None
    if getattr(advice, "context_candidates", 0):
        context_summary = t(
            "decision.context.summary",
            lang=lang,
            candidates=advice.context_candidates,
            selected=getattr(advice, "context_selected", 0),
            before=getattr(advice, "context_tokens_before", 0),
            after=getattr(advice, "context_tokens_after", 0),
            saved=getattr(advice, "context_tokens_saved", 0),
        )

    risks = []
    if getattr(advice, "change_risk", None):
        risk = _localized_value("risk", advice.change_risk, lang=lang) or advice.change_risk
        confidence = getattr(advice, "change_risk_confidence", None)
        risks.append(
            t(
                "decision.risk.change_confidence" if confidence is not None else "decision.risk.change",
                lang=lang,
                risk=risk,
                confidence=f"{confidence:.2f}" if confidence is not None else "",
            )
        )
    if getattr(advice, "security_review", None) == "required":
        risks.append(t("decision.risk.security", lang=lang))
    if getattr(advice, "context_escalated", ()):
        risks.append(t("decision.risk.context_fail_open", lang=lang, count=len(advice.context_escalated)))
    if getattr(advice, "escalation_required", False):
        risks.append(t("decision.risk.reasoning_escalated", lang=lang))

    if advice.action in {
        "prepare",
        "verify",
        "advance-criterion",
        "submit-pr",
        "approve",
        "accept-criteria",
        "mark-deployed",
        "transition",
    }:
        boundary = t("decision.return.reinspect", lang=lang)
    else:
        boundary = t("decision.return.human_validation", lang=lang)

    title = t(f"decision.title.{advice.action}", lang=lang)
    if title == f"decision.title.{advice.action}":
        title = advice.summary

    focus = _localized_value("focus", getattr(advice, "validation_focus", None), lang=lang)

    return DecisionCard(
        title=title,
        rationale=tuple(rationale),
        will_do=will_do,
        will_not_do=will_not_do,
        executor=runtime,
        intelligence=intelligence,
        context_summary=context_summary,
        risk_summary=tuple(risks),
        validation_focus=focus,
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
