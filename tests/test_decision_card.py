from types import SimpleNamespace

from agora_ai_sdlc.decision_card import build_decision_card, render_decision_card
from agora_ai_sdlc.guided import GuidedDecision


def decision():
    return GuidedDecision(
        swarm="delivery",
        work="issue-26",
        title="Implement idempotent retries",
        method="ai-sdlc",
        actor="project:developer",
        role="developer",
        state="construction",
        target="operations",
        gate="construction-verified",
        blockers=("blocked",),
        messages=("Complete verification.",),
        missing_artifacts=("deployment-unit",),
        missing_evidence=("test-suite",),
        missing_approvals=(),
        unsatisfied_criteria=("ac-2",),
        git_issues=(),
        clarification_issues=(),
    )


def advice():
    return SimpleNamespace(
        action="prepare",
        summary="Prepare the remaining Construction outputs.",
        source="laya",
        reasoning_tier="local",
        confidence=0.96,
        recommended_runtime=SimpleNamespace(label="Ollama · qwen3:8b [local]"),
        escalation_required=False,
        context_candidates=12,
        context_selected=5,
        context_tokens_before=8400,
        context_tokens_after=2900,
        context_tokens_saved=5500,
        context_escalated=("src/uncertain.py",),
        security_review="required",
        change_risk="moderate",
        change_risk_confidence=0.93,
        validation_focus="security",
        validation_focus_confidence=0.91,
    )


def test_decision_card_exposes_why_scope_boundaries_and_context():
    card = build_decision_card(decision(), advice())

    assert card.executor == "Ollama · qwen3:8b [local]"
    assert any("deployment-unit" in item for item in card.rationale)
    assert any("5500" in card.context_summary for _ in [0])
    assert any("security" in item.casefold() for item in card.risk_summary)
    assert any("moderate" in item.casefold() for item in card.risk_summary)
    assert card.validation_focus == "security"
    assert any("approval" in item.casefold() for item in card.will_not_do)

    rendered = render_decision_card(card)
    assert "Proposed decision" in rendered
    assert "If confirmed, Agora will" in rendered
    assert "Boundaries" in rendered
    assert "Validation focus: security" in rendered
    assert "Next checkpoint" in rendered


def test_decision_card_spanish_preserves_operational_detail():
    rendered = render_decision_card(build_decision_card(decision(), advice()), lang="es")

    assert "Decisión propuesta" in rendered
    assert "Contexto" in rendered
    assert "Ollama · qwen3:8b [local]" in rendered
    assert "~8400 → ~2900 tokens" in rendered


def test_final_criterion_acceptance_card_is_explicit_human_action():
    final_decision = GuidedDecision(
        swarm="delivery",
        work="issue-26",
        title="Deliver issue",
        method="ai-sdlc",
        actor="project:product-owner",
        role="product-owner",
        state="operations",
        target="completed",
        gate="completion",
        blockers=("unsatisfied=[source-issue]",),
        messages=("Complete criteria.",),
        unsatisfied_criteria=("source-issue",),
    )
    final_advice = SimpleNamespace(
        action="accept-criteria",
        summary="Accept completed criteria.",
        source="deterministic",
        reasoning_tier=None,
        confidence=None,
        recommended_runtime=None,
        escalation_required=False,
        context_candidates=0,
        context_selected=0,
        context_tokens_before=0,
        context_tokens_after=0,
        context_tokens_saved=0,
        context_escalated=(),
        security_review=None,
        change_risk=None,
        validation_focus=None,
    )

    card = build_decision_card(final_decision, final_advice, lang="es")
    rendered = render_decision_card(card, lang="es")

    assert "aceptación explícita del Product Owner" in card.title
    assert any("criterios completados" in item for item in card.will_do)
    assert "Inteligencia: determinístico/Core" in rendered
    assert "Executor:" not in rendered
