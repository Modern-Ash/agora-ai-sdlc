"""Interactive terminal loop for guided AI-SDLC decisions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agora_ai_sdlc.guided import GuidedDecision, inspect_next, render
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
) -> RuntimeDiscovery | None:
    runtimes = _responsive_runtimes(root)
    if not runtimes:
        output_fn("No responsive AI CLI runtime was detected.")
        return None

    output_fn("")
    output_fn("Available assistants")
    for index, runtime in enumerate(runtimes, start=1):
        selected = " (current)" if current is not None and runtime.id == current.id else ""
        output_fn(f"  {index}. {runtime.name:<12} ✓ responsive{selected}")
    output_fn("  X. Cancel")

    while True:
        answer = input_fn("Select assistant: ").strip().casefold()
        if answer in {"x", "q", "cancel"}:
            return current
        try:
            index = int(answer)
        except ValueError:
            output_fn("Choose a runtime number or X.")
            continue
        if 1 <= index <= len(runtimes):
            runtime = runtimes[index - 1]
            output_fn(f"Selected assistant: {runtime.name}")
            return runtime
        output_fn("Choose one of the listed runtime numbers.")


def _render_review(decision: GuidedDecision, output_fn: Callable[[str], None]) -> None:
    output_fn("")
    output_fn("Readiness review")
    output_fn(f"  Work: {decision.swarm}/{decision.work}")
    output_fn(f"  Stage: {decision.state or 'unknown'} -> {decision.target or '-'}")
    output_fn(f"  Gate: {decision.gate or '-'}")
    if decision.missing_artifacts:
        output_fn("  Missing artifacts: " + ", ".join(decision.missing_artifacts))
    if decision.clarification_issues:
        output_fn("  Clarifications: " + ", ".join(decision.clarification_issues))
    if decision.missing_evidence:
        output_fn("  Missing evidence: " + ", ".join(decision.missing_evidence))
    if decision.missing_approvals:
        output_fn("  Human approvals: " + ", ".join(decision.missing_approvals))
    if not decision.messages:
        output_fn("  No remaining guided obligations were projected.")


def _render_prepare_handoff(
    decision: GuidedDecision,
    runtime: RuntimeDiscovery,
    output_fn: Callable[[str], None],
) -> None:
    output_fn("")
    output_fn(f"Prepare with {runtime.name}")
    output_fn(
        "  The assistant may inspect repository context, draft required non-authoritative artifacts, "
        "and analyze clarifications."
    )
    output_fn("  It must return before any human approval is recorded.")
    if decision.missing_artifacts:
        output_fn("  Prepare: " + ", ".join(decision.missing_artifacts))
    if decision.clarification_issues:
        output_fn("  Analyze clarification requirement before transition.")
    output_fn("")
    output_fn(
        "  Runtime selection is active for this session. Provider-specific execution remains "
        "delegated to the installed guided skill."
    )


def run_interactive(
    root: Path,
    *,
    swarm: str | None = None,
    work: str | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> GuidedSessionResult:
    """Run a human-driven guided loop. Core remains authoritative and no approval is automated."""

    selected_runtime: RuntimeDiscovery | None = None

    while True:
        decision = inspect_next(root, swarm=swarm, work=work)
        output_fn(render(decision))

        if decision is None:
            return GuidedSessionResult("clear", selected_runtime.id if selected_runtime else None)

        output_fn("")
        if selected_runtime is not None:
            output_fn(f"Active assistant: {selected_runtime.name}")
        output_fn("[P] Prepare with AI  [R] Review context  [D] Governance details")
        output_fn("[C] Change agent     [X] Exit")

        answer = input_fn("Select: ").strip().casefold()

        if answer in {"x", "q", "exit"}:
            return GuidedSessionResult("exit", selected_runtime.id if selected_runtime else None)

        if answer in {"d", "details"}:
            output_fn("")
            output_fn(render(decision, expert=True))
            continue

        if answer in {"r", "review"}:
            _render_review(decision, output_fn)
            continue

        if answer in {"c", "change"}:
            selected_runtime = _select_runtime(
                root,
                input_fn=input_fn,
                output_fn=output_fn,
                current=selected_runtime,
            )
            continue

        if answer in {"p", "prepare"}:
            if selected_runtime is None:
                selected_runtime = _select_runtime(
                    root,
                    input_fn=input_fn,
                    output_fn=output_fn,
                )
            if selected_runtime is None:
                continue
            _render_prepare_handoff(decision, selected_runtime, output_fn)
            output_fn("")
            output_fn("[R] Review context  [C] Change agent  [B] Back  [X] Exit")
            follow_up = input_fn("Select: ").strip().casefold()
            if follow_up in {"x", "q", "exit"}:
                return GuidedSessionResult("exit", selected_runtime.id)
            if follow_up in {"c", "change"}:
                selected_runtime = _select_runtime(
                    root,
                    input_fn=input_fn,
                    output_fn=output_fn,
                    current=selected_runtime,
                )
            elif follow_up in {"r", "review"}:
                _render_review(decision, output_fn)
            continue

        output_fn("Choose P, R, D, C or X.")
