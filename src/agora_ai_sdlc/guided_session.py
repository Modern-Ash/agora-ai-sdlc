"""Interactive terminal loop for guided AI-SDLC decisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agora_ai_sdlc.executor_recovery import ExecutorRecoveryChoice, recovery_choices
from agora_ai_sdlc.guided import GuidedDecision, inspect_next, render
from agora_ai_sdlc.i18n import t
from agora_ai_sdlc.opencode_runner import list_available_models
from agora_ai_sdlc.runtime_discovery import discover_runtimes


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
    choices = recovery_choices(
        root,
        discovery=discover_runtimes,
        model_lister=list_available_models,
    )
    if not choices:
        output_fn(t("session.no_runtime", lang=lang))
        return None

    output_fn("")
    output_fn(t("session.available", lang=lang))
    for index, choice in enumerate(choices, start=1):
        selected = (
            f" ({t('session.current', lang=lang)})"
            if current is not None
            and choice.agent == current.agent
            and choice.model == current.model
            else ""
        )
        output_fn(
            f"  {index}. {choice.label} ✓ {t('session.responsive', lang=lang)}{selected}"
        )
    output_fn(f"  X. {t('session.cancel', lang=lang)}")

    while True:
        answer = input_fn(t("session.select_assistant", lang=lang)).strip().casefold()
        if answer in {"x", "q", "cancel"}:
            return current
        try:
            index = int(answer)
        except ValueError:
            output_fn(t("session.choose_number_x", lang=lang))
            continue
        if 1 <= index <= len(choices):
            choice = choices[index - 1]
            output_fn(t("session.selected", lang=lang, runtime=choice.label))
            return choice
        output_fn(t("session.choose_listed", lang=lang))


def _render_review(decision: GuidedDecision, output_fn: Callable[[str], None], *, lang: str = "en") -> None:
    output_fn("")
    output_fn(t("session.review", lang=lang))
    output_fn(f"  Work: {decision.swarm}/{decision.work}")
    output_fn(f"  Stage: {decision.state or 'unknown'} -> {decision.target or '-'}")
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
    """Run a human-driven guided loop. Core remains authoritative and no approval is automated."""

    selected_runtime: ExecutorRecoveryChoice | None = None

    while True:
        decision = inspect_next(root, swarm=swarm, work=work, lang=lang)
        output_fn(render(decision, show_actions=False, lang=lang))

        if decision is None:
            return GuidedSessionResult(
                "clear",
                selected_runtime.agent if selected_runtime else None,
                selected_runtime.model if selected_runtime else None,
            )

        output_fn("")
        if selected_runtime is not None:
            output_fn(t("session.active", lang=lang, runtime=selected_runtime.label))
        output_fn(t("session.menu", lang=lang))
        output_fn(t("session.menu2", lang=lang))

        answer = input_fn(t("session.select", lang=lang)).strip().casefold()

        if answer in {"x", "q", "exit"}:
            return GuidedSessionResult(
                "exit",
                selected_runtime.agent if selected_runtime else None,
                selected_runtime.model if selected_runtime else None,
            )

        if answer in {"d", "details"}:
            output_fn("")
            output_fn(render(decision, expert=True, lang=lang))
            continue

        if answer in {"r", "review"}:
            _render_review(decision, output_fn, lang=lang)
            continue

        if answer in {"c", "change"}:
            selected_runtime = _select_runtime(
                root,
                input_fn=input_fn,
                output_fn=output_fn,
                current=selected_runtime,
                lang=lang,
            )
            continue

        if answer in {"p", "prepare"}:
            if selected_runtime is None:
                selected_runtime = _select_runtime(
                    root,
                    input_fn=input_fn,
                    output_fn=output_fn,
                    lang=lang,
                )
            if selected_runtime is None:
                continue
            _render_prepare_handoff(decision, selected_runtime, output_fn, lang=lang)
            output_fn("")
            output_fn(t("session.followup", lang=lang))
            follow_up = input_fn(t("session.select", lang=lang)).strip().casefold()
            if follow_up in {"x", "q", "exit"}:
                return GuidedSessionResult(
                    "exit",
                    selected_runtime.agent,
                    selected_runtime.model,
                )
            if follow_up in {"c", "change"}:
                selected_runtime = _select_runtime(
                    root,
                    input_fn=input_fn,
                    output_fn=output_fn,
                    current=selected_runtime,
                    lang=lang,
                )
            elif follow_up in {"r", "review"}:
                _render_review(decision, output_fn, lang=lang)
            continue

        output_fn(t("session.choose", lang=lang))
