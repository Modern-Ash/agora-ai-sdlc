"""Deterministic human progress rendering from known workflow facts.

Bars describe completed contract steps/stages only. They never estimate model effort,
elapsed task completion, token use, cost, or wall-clock time remaining.
"""

from __future__ import annotations

START_STEPS = (
    "start.inspect",
    "start.workspace-ready",
    "start.runtime-ready",
    "start.project-ready",
    "start.work-ready",
    "start.issue-read",
    "start.intent-ready",
    "start.pathway",
    "start.handoff",
    "start.executor-launch",
    "start.executor-complete",
    "start.prepared",
)
_START_ALIASES = {
    "start.issue-reused": "start.issue-read",
    "start.executor-skipped-launch": "start.executor-launch",
    "start.executor-skipped-complete": "start.executor-complete",
    "start.deterministic-inception": "start.executor-launch",
    "start.deterministic-complete": "start.executor-complete",
}
LIFECYCLE_STAGES = ("inception", "construction", "operations", "completed")


def _bar(completed: int, total: int, *, width: int = 10) -> str:
    if total <= 0:
        return "[" + "░" * width + "]"
    completed = min(max(completed, 0), total)
    filled = round(width * completed / total)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def start_progress(code: str, label: str) -> str | None:
    """Render one Start contract event as deterministic completed/total progress."""

    logical = _START_ALIASES.get(code, code)
    if logical not in START_STEPS:
        return None
    completed = START_STEPS.index(logical) + 1
    total = len(START_STEPS)
    percent = round(100 * completed / total)
    return f"{_bar(completed, total)} {percent:>3}%  {completed}/{total}  {label}"


def lifecycle_progress(state: str | None) -> str:
    """Render durable lifecycle position without implying time/effort completion."""

    if state not in LIFECYCLE_STAGES:
        return f"{_bar(0, len(LIFECYCLE_STAGES))} ?/{len(LIFECYCLE_STAGES)}  {state or 'unknown'}"
    completed = LIFECYCLE_STAGES.index(state) + 1
    total = len(LIFECYCLE_STAGES)
    return f"{_bar(completed, total)} {completed}/{total}  {state}"
