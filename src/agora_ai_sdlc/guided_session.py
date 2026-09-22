"""Interactive terminal loop for guided AI-SDLC decisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agora_ai_sdlc.guided import GuidedDecision, inspect_next, render
from agora_ai_sdlc.i18n import t
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes


@dataclass(frozen=True)
class GuidedSessionResult:
    reason: str
    selected_runtime: str | None = None


def _responsive_runtimes(root: Path) -> tuple[RuntimeDiscovery, ...]:
    return tuple(item for item in discover_runtimes(root) if item.installed and item.responsive)


def _select_runtime(
    root: Path,
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    current: RuntimeDiscovery | None = None,
    lang: str = "en",
) -> RuntimeDiscovery | None:
    runtimes = _responsive_runtimes(root)
    if not runtimes:
        output_fn(t("session.no_runtime", lang=lang))
        return None

    output_fn("")
    output_fn(t("session.available", lang=lang))
    for index, runtime in enumerate(runtimes, start=1):
        selected = f" ({t('session.current', lang=lang)})" if current is not None and runtime.id == current.id else ""
        output_fn(f"  {index}. {runtime.name:<12} ✓ {t('session.responsive', lang=lang)}{selected}")
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
        if 1 <= index <= len(runtimes):
            runtime = runtimes[index - 1]
            output_fn(t("session.selected", lang=lang, runtime=runtime.name))
            return runtime
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
    runtime: RuntimeDiscovery,
    output_fn: Callable[[str], None],
    *,
    lang: str = "en",
) -> None:
    output_fn("")
    output_fn(t("session.prepare_with", lang=lang, runtime=runtime.name))
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

    selected_runtime: RuntimeDiscovery | None = None

    while True:
        decision = inspect_next(root, swarm=swarm, work=work, lang=lang)
        output_fn(render(decision, show_actions=False, lang=lang))

        if decision is None:
            return GuidedSessionResult("clear", selected_runtime.id if selected_runtime else None)

        output_fn("")
        if selected_runtime is not None:
            output_fn(t("session.active", lang=lang, runtime=selected_runtime.name))
        output_fn(t("session.menu", lang=lang))
        output_fn(t("session.menu2", lang=lang))

        answer = input_fn(t("session.select", lang=lang)).strip().casefold()

        if answer in {"x", "q", "exit"}:
            return GuidedSessionResult("exit", selected_runtime.id if selected_runtime else None)

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
                return GuidedSessionResult("exit", selected_runtime.id)
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
