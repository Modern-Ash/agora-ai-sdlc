"""Interactive terminal loop for guided AI-SDLC decisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agora_ai_sdlc.decision_card import build_decision_card, render_decision_card
from agora_ai_sdlc.executor_recovery import ExecutorRecoveryChoice, select_executor_model
from agora_ai_sdlc.guided import GuidedDecision, inspect_next, render
from agora_ai_sdlc.guided_execution import execute_guided_preparation
from agora_ai_sdlc.i18n import t
from agora_ai_sdlc.opencode_runner import list_available_models, list_ollama_agent_models
from agora_ai_sdlc.runtime_discovery import discover_runtimes
from agora_ai_sdlc.wizard import build_wizard_view, render_wizard, save_answer
from agora_ai_sdlc.wizard_actions import execute_in_session_action
from agora_ai_sdlc.workflow_advisor import advise_workflow


@dataclass(frozen=True)
class GuidedSessionResult:
    reason: str
    selected_runtime: str | None = None
    selected_model: str | None = None


def _select_runtime(
    root: Path,
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    current: ExecutorRecoveryChoice | None = None,
    lang: str = "en",
) -> ExecutorRecoveryChoice | None:
    choice = select_executor_model(
        root,
        input_fn=input_fn,
        output_fn=output_fn,
        current=current,
        lang=lang,
        discovery=discover_runtimes,
        model_lister=list_available_models,
        ollama_model_lister=list_ollama_agent_models,
    )
    if choice is None:
        output_fn(t("session.no_runtime", lang=lang))
        return current
    output_fn(t("session.selected", lang=lang, runtime=choice.label))
    return choice


def _render_review(decision: GuidedDecision, output_fn: Callable[[str], None], *, lang: str = "en") -> None:
    output_fn("")
    output_fn(t("session.review", lang=lang))
    output_fn(f"  {t('session.work', lang=lang)}: {decision.swarm}/{decision.work}")
    output_fn(
        f"  {t('session.stage', lang=lang)}: {decision.state or t('guided.unknown', lang=lang)} -> {decision.target or '-'}"
    )
    output_fn(f"  {t('session.gate', lang=lang)}: {decision.gate or '-'}")
    if decision.missing_artifacts:
        output_fn(f"  {t('session.missing_artifacts', lang=lang)}: " + ", ".join(decision.missing_artifacts))
    if decision.clarification_issues:
        output_fn(f"  {t('session.clarifications', lang=lang)}: " + ", ".join(decision.clarification_issues))
    if decision.missing_evidence:
        output_fn(f"  {t('session.missing_evidence', lang=lang)}: " + ", ".join(decision.missing_evidence))
    if decision.missing_approvals:
        output_fn(f"  {t('session.human_approvals', lang=lang)}: " + ", ".join(decision.missing_approvals))
    if not decision.messages:
        output_fn("  " + t("session.no_obligations", lang=lang))


def _render_prepare_handoff(
    decision: GuidedDecision,
    runtime: ExecutorRecoveryChoice,
    output_fn: Callable[[str], None],
    *,
    lang: str = "en",
) -> None:
    output_fn("")
    output_fn(t("session.prepare_with", lang=lang, runtime=runtime.label))
    output_fn("  " + t("session.prepare_desc", lang=lang))
    output_fn("  " + t("session.return_before_approval", lang=lang))
    if decision.missing_artifacts:
        output_fn(f"  {t('session.prepare', lang=lang)}: " + ", ".join(decision.missing_artifacts))
    if decision.clarification_issues:
        output_fn("  " + t("session.analyze_clarification", lang=lang))
    output_fn("")
    output_fn("  " + t("session.runtime_note", lang=lang))


def run_interactive(
    root: Path,
    *,
    swarm: str | None = None,
    work: str | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    lang: str = "en",
) -> GuidedSessionResult:
    """Run one continuous, transparent delivery wizard over authoritative Core state."""

    selected_runtime: ExecutorRecoveryChoice | None = None

    while True:
        decision = inspect_next(root, swarm=swarm, work=work, lang=lang)
        if decision is None:
            output_fn("Agora AI-SDLC")
            output_fn("")
            output_fn(t("guided.none", lang=lang))
            return GuidedSessionResult(
                "clear",
                selected_runtime.agent if selected_runtime else None,
                selected_runtime.model if selected_runtime else None,
            )

        view = build_wizard_view(root, decision)
        output_fn("")
        output_fn(render_wizard(view, lang=lang))

        # Material ambiguity is handled as part of the same wizard. No prompt
        # engineering or secondary command is exposed to the user.
        if view.questions:
            question = view.questions[0]
            output_fn("")
            output_fn(t("wizard.question_title", lang=lang))
            output_fn(f"  {question.text}")
            reason = (
            t("wizard.question_material_reason", lang=lang)
            if question.reason == "This answer removes a material ambiguity before AI enriches the next artifact."
            else question.reason
        )
        output_fn(f"  {t('wizard.why', lang=lang)}: {reason}")
            answer = input_fn(t("wizard.answer", lang=lang)).strip()
            if answer.casefold() in {"x", "q", "exit"}:
                return GuidedSessionResult(
                    "exit",
                    selected_runtime.agent if selected_runtime else None,
                    selected_runtime.model if selected_runtime else None,
                )
            if answer.casefold() in {"d", "details"}:
                output_fn("")
                output_fn(render(decision, expert=True, show_commands=True, lang=lang))
                continue
            if not answer:
                output_fn(t("wizard.answer_required", lang=lang))
                continue
            path = save_answer(root, decision.work, question, answer)
            output_fn(t("wizard.answer_saved", lang=lang, path=str(path.relative_to(root))))
            output_fn(t("wizard.recalculate", lang=lang))
            continue

        advice = advise_workflow(root, decision)
        if selected_runtime is None and advice.recommended_runtime is not None:
            selected_runtime = advice.recommended_runtime

        output_fn("")
        output_fn(render_decision_card(build_decision_card(decision, advice, lang=lang), lang=lang))

        output_fn("")
        output_fn(t("wizard.actions", lang=lang))
        answer = input_fn(t("wizard.confirm", lang=lang)).strip().casefold()

        if answer in {"x", "q", "exit"}:
            return GuidedSessionResult(
                "exit",
                selected_runtime.agent if selected_runtime else None,
                selected_runtime.model if selected_runtime else None,
            )

        if answer in {"d", "details"}:
            output_fn("")
            output_fn(render(decision, expert=True, show_commands=True, lang=lang))
            continue

        if answer in {"a", "adjust", "c", "change"}:
            selected_runtime = _select_runtime(
                root,
                input_fn=input_fn,
                output_fn=output_fn,
                current=selected_runtime,
                lang=lang,
            )
            continue

        if answer not in {"", "y", "yes", "confirm", "ok"}:
            output_fn(t("wizard.choose", lang=lang))
            continue

        if advice.action != "prepare":
            if advice.action == "review":
                _render_review(decision, output_fn, lang=lang)
                output_fn("")
                output_fn(t("wizard.review_boundary", lang=lang))
                continue
            try:
                action_result = execute_in_session_action(root, decision)
            except (OSError, RuntimeError, ValueError, PermissionError) as error:
                output_fn(t("wizard.node_action_failed", lang=lang, error=str(error)))
                continue
            output_fn("")
            summary = t(f"wizard.action_result.{action_result.kind}", lang=lang, **dict(action_result.details))
            output_fn(t("wizard.node_action_complete", lang=lang, summary=summary))
            output_fn(t("session.reinspect", lang=lang))
            continue

        if selected_runtime is None:
            selected_runtime = _select_runtime(
                root,
                input_fn=input_fn,
                output_fn=output_fn,
                lang=lang,
            )
        if selected_runtime is None:
            continue

        output_fn("")
        output_fn(t("session.executing", lang=lang, runtime=selected_runtime.label))
        try:
            result = execute_guided_preparation(
                root,
                decision,
                runtime_id=selected_runtime.agent,
                model=selected_runtime.model,
            )
        except (OSError, RuntimeError, ValueError) as error:
            output_fn(t("session.execution_failed", lang=lang, error=str(error)))
            output_fn(t("session.execution_recovery", lang=lang))
            continue
        output_fn(t("session.execution_complete", lang=lang, runtime=result.runtime))
        output_fn(t("session.reinspect", lang=lang))
