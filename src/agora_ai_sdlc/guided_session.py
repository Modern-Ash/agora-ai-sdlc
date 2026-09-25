"""Interactive terminal loop for guided AI-SDLC decisions."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic

from agora_ai_sdlc.decision_card import build_decision_card, render_decision_card
from agora_ai_sdlc.executor_recovery import ExecutorRecoveryChoice, select_executor_model
from agora_ai_sdlc.guided import GuidedDecision, inspect_next, render
from agora_ai_sdlc.guided_execution import execute_guided_preparation
from agora_ai_sdlc.i18n import t
from agora_ai_sdlc.iteration_status import inspect_iteration, render_terminal_summary
from agora_ai_sdlc.opencode_runner import list_available_models, list_ollama_agent_models
from agora_ai_sdlc.runtime_discovery import discover_runtimes
from agora_ai_sdlc.wizard import build_wizard_view, render_wizard, save_answer
from agora_ai_sdlc.wizard_actions import execute_in_session_action
from agora_ai_sdlc.workflow_advisor import advise_workflow


class _ProgressDisplay:
    """Animate one in-place status line on TTYs and stay concise in logs/tests."""

    _frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(
        self,
        *,
        output_fn: Callable[[str], None],
        lang: str,
        runtime: str,
        interval_seconds: float = 0.1,
    ) -> None:
        self._output_fn = output_fn
        self._lang = lang
        self._runtime = runtime
        self._interval_seconds = interval_seconds
        self._tty = output_fn is print and sys.stdout.isatty()
        self._message = ""
        self._last_fallback_stage: str | None = None
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._rendered_width = 0
        self._started_at: float | None = None

    def start(self) -> None:
        if not self._tty or self._thread is not None:
            return
        self._started_at = monotonic()
        self._thread = Thread(target=self._animate, name="agora-flow-spinner", daemon=True)
        self._thread.start()

    def update(self, stage: str) -> None:
        stage_name, separator, detail = stage.partition(":")
        if stage_name == "executor_wait" and separator and detail:
            message = t(
                "session.progress.executor_milestone",
                lang=self._lang,
                runtime=self._runtime,
                detail=detail,
            )
        else:
            message = t(f"session.progress.{stage_name}", lang=self._lang, runtime=self._runtime)
        if not self._tty:
            if stage != self._last_fallback_stage:
                self._output_fn(message)
                self._last_fallback_stage = stage
            return
        with self._lock:
            self._message = message

    def stop(self) -> None:
        if not self._tty:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
        self._clear_line()

    def _animate(self) -> None:
        index = 0
        while not self._stop.wait(self._interval_seconds):
            with self._lock:
                message = self._message
            if not message:
                continue
            elapsed = max(0, int(monotonic() - self._started_at)) if self._started_at is not None else 0
            minutes, seconds = divmod(elapsed, 60)
            text = f"{self._frames[index % len(self._frames)]} [{minutes:02d}:{seconds:02d}] {message}"
            self._rendered_width = max(self._rendered_width, len(text))
            sys.stdout.write("\r" + text.ljust(self._rendered_width))
            sys.stdout.flush()
            index += 1

    def _clear_line(self) -> None:
        if self._rendered_width:
            sys.stdout.write("\r" + (" " * self._rendered_width) + "\r\n")
            sys.stdout.flush()


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


def _render_execution_error(
    error: BaseException,
    runtime: ExecutorRecoveryChoice,
    output_fn: Callable[[str], None],
    *,
    lang: str,
) -> None:
    """Render executor failures as readable console diagnostics instead of one long exception line."""

    text = str(error).strip()
    diagnostic = None
    durable = None

    diagnostic_marker = " Executor diagnostic: "
    if diagnostic_marker in text:
        text, diagnostic = text.rsplit(diagnostic_marker, 1)
        diagnostic = diagnostic.rstrip(".")

    durable_marker = " Durable diagnostics: "
    if durable_marker in text:
        prefix, remainder = text.split(durable_marker, 1)
        resume_marker = ". Resume with:"
        if resume_marker in remainder:
            durable = remainder.split(resume_marker, 1)[0].strip().rstrip(".")
        text = prefix.rstrip(".")

    output_fn("")
    output_fn("╭─ " + t("session.execution_error_title", lang=lang, runtime=runtime.label))
    if diagnostic:
        output_fn("│ " + t("session.execution_error_reason", lang=lang, reason=diagnostic))
    else:
        output_fn("│ " + t("session.execution_error_reason", lang=lang, reason=text))
    if durable:
        output_fn("│ " + t("session.execution_error_durable", lang=lang, path=durable))
    output_fn("│ " + t("session.execution_error_preserved", lang=lang))
    output_fn("╰" + "─" * 72)


def _decision_fingerprint(decision: GuidedDecision) -> tuple[object, ...]:
    """Capture the authoritative obligations that must change after useful preparation."""

    return (
        decision.state,
        decision.target,
        decision.gate,
        decision.blockers,
        decision.missing_artifacts,
        decision.missing_evidence,
        decision.missing_approvals,
        decision.unsatisfied_criteria,
        decision.git_issues,
        decision.clarification_issues,
        decision.observed_artifacts,
        decision.ready_for_human_approval,
        decision.ready_to_transition,
    )


def _confirm_current_decision(
    root: Path,
    decision: GuidedDecision,
    *,
    selected_runtime: ExecutorRecoveryChoice | None,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    lang: str,
    retry: bool = False,
) -> tuple[str, ExecutorRecoveryChoice | None]:
    """Confirm the current decision without re-reading Core or re-running Laya."""

    while True:
        output_fn("")
        if selected_runtime is not None:
            output_fn(t("wizard.actions_selected", lang=lang, runtime=selected_runtime.label))
        elif retry:
            output_fn(t("wizard.actions_retry", lang=lang))
        else:
            output_fn(t("wizard.actions", lang=lang))
        answer = input_fn(t("wizard.confirm", lang=lang)).strip().casefold()

        if answer in {"x", "q", "exit"}:
            return "exit", selected_runtime

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

        return "confirm", selected_runtime


def run_interactive(
    root: Path,
    *,
    swarm: str | None = None,
    work: str | None = None,
    initial_runtime: ExecutorRecoveryChoice | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    lang: str = "en",
) -> GuidedSessionResult:
    """Run one continuous, transparent delivery wizard over authoritative Core state."""

    selected_runtime: ExecutorRecoveryChoice | None = initial_runtime
    failed_runtimes: set[tuple[str, str | None]] = set()
    previous_execution_fingerprint: tuple[object, ...] | None = None
    previous_execution_result_path: str | None = None

    while True:
        decision = inspect_next(root, swarm=swarm, work=work, lang=lang)
        if decision is None:
            status = inspect_iteration(root, swarm=swarm, work=work)
            output_fn("")
            output_fn(render_terminal_summary(status, lang=lang))
            reason = "completed" if status.state == "completed" else "clear"
            return GuidedSessionResult(
                reason,
                selected_runtime.agent if selected_runtime else None,
                selected_runtime.model if selected_runtime else None,
            )

        if (
            previous_execution_fingerprint is not None
            and _decision_fingerprint(decision) == previous_execution_fingerprint
        ):
            output_fn("")
            output_fn(
                t(
                    "session.no_progress",
                    lang=lang,
                    result=previous_execution_result_path or "-",
                )
            )
            if selected_runtime is not None:
                failed_runtimes.add((selected_runtime.agent, selected_runtime.model))
            selected_runtime = None
            previous_execution_fingerprint = None
            previous_execution_result_path = None
            confirmation, selected_runtime = _confirm_current_decision(
                root,
                decision,
                selected_runtime=None,
                input_fn=input_fn,
                output_fn=output_fn,
                lang=lang,
                retry=True,
            )
            if confirmation == "exit":
                return GuidedSessionResult("exit")
            continue

        previous_execution_fingerprint = None
        previous_execution_result_path = None

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

        output_fn(t("session.analyzing", lang=lang))
        advice = advise_workflow(root, decision)
        if selected_runtime is None and advice.recommended_runtime is not None:
            recommended_key = (advice.recommended_runtime.agent, advice.recommended_runtime.model)
            if recommended_key not in failed_runtimes:
                selected_runtime = advice.recommended_runtime

        output_fn("")
        output_fn(render_decision_card(build_decision_card(decision, advice, lang=lang), lang=lang))

        confirmation, selected_runtime = _confirm_current_decision(
            root,
            decision,
            selected_runtime=selected_runtime,
            input_fn=input_fn,
            output_fn=output_fn,
            lang=lang,
        )
        if confirmation == "exit":
            return GuidedSessionResult(
                "exit",
                selected_runtime.agent if selected_runtime else None,
                selected_runtime.model if selected_runtime else None,
            )

        if advice.action != "prepare":
            if advice.action == "review":
                _render_review(decision, output_fn, lang=lang)
                output_fn("")
                output_fn(t("wizard.review_boundary", lang=lang))
                return GuidedSessionResult(
                    "review",
                    selected_runtime.agent if selected_runtime else None,
                    selected_runtime.model if selected_runtime else None,
                )
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

        restart_before_execution = False
        while True:
            if selected_runtime is None:
                selected_runtime = _select_runtime(
                    root,
                    input_fn=input_fn,
                    output_fn=output_fn,
                    lang=lang,
                )
            if selected_runtime is None:
                confirmation, selected_runtime = _confirm_current_decision(
                    root,
                    decision,
                    selected_runtime=None,
                    input_fn=input_fn,
                    output_fn=output_fn,
                    lang=lang,
                    retry=True,
                )
                if confirmation == "exit":
                    return GuidedSessionResult("execution-failed")
                continue

            current_decision = inspect_next(root, swarm=swarm, work=work, lang=lang)
            if current_decision is None or _decision_fingerprint(current_decision) != _decision_fingerprint(decision):
                output_fn("")
                output_fn(t("session.reinspect", lang=lang))
                restart_before_execution = True
                break

            output_fn("")
            output_fn(t("session.executing", lang=lang, runtime=selected_runtime.label))
            progress = _ProgressDisplay(output_fn=output_fn, lang=lang, runtime=selected_runtime.label)
            progress.start()
            execution_error: BaseException | None = None
            try:
                result = execute_guided_preparation(
                    root,
                    decision,
                    runtime_id=selected_runtime.agent,
                    model=selected_runtime.model,
                    progress_fn=progress.update,
                )
            except (OSError, RuntimeError, ValueError) as error:
                execution_error = error
            finally:
                progress.stop()

            if execution_error is None:
                break

            failed_runtimes.add((selected_runtime.agent, selected_runtime.model))
            _render_execution_error(
                execution_error,
                selected_runtime,
                output_fn,
                lang=lang,
            )
            selected_runtime = None
            confirmation, selected_runtime = _confirm_current_decision(
                root,
                decision,
                selected_runtime=None,
                input_fn=input_fn,
                output_fn=output_fn,
                lang=lang,
                retry=True,
            )
            if confirmation == "exit":
                return GuidedSessionResult("execution-failed")

        if restart_before_execution:
            continue

        previous_execution_fingerprint = _decision_fingerprint(decision)
        previous_execution_result_path = result.result_path
        output_fn(t("session.execution_complete", lang=lang, runtime=result.runtime))
        output_fn(t("session.reinspect", lang=lang))
