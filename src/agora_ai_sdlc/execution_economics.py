"""Non-authoritative execution economics telemetry.

Agora Core remains the source of truth for lifecycle and authoritative usage.
This ledger records provider-neutral routing/execution facts that help explain
why a tier was selected and how often each economic tier was actually invoked.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agora_ai_sdlc.runtime_adapter import sanitize
from agora_ai_sdlc.runtime_selection import Budget, budget_from_core

SCHEMA = "agora-ai-sdlc/execution-economics/v1"


@dataclass(frozen=True)
class EconomicsEvent:
    event: str
    work: str
    tier: str | None
    agent: str | None
    model: str | None
    purpose: str | None = None
    reason: str | None = None
    exit_code: int | None = None
    core_usage: dict[str, Any] | None = None
    at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema"] = SCHEMA
        data["at"] = self.at or datetime.now(UTC).isoformat()
        if data.get("reason"):
            data["reason"] = sanitize(str(data["reason"]))[:500]
        return data


def ledger_path(root: Path, work: str) -> Path:
    return root / ".agora" / "ai-sdlc" / "economics" / work / "EVENTS.jsonl"


def record_event(root: Path, event: EconomicsEvent) -> str:
    path = ledger_path(root, event.work)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
    return str(path)


def load_events(root: Path, work: str) -> tuple[dict[str, Any], ...]:
    path = ledger_path(root, work)
    if not path.is_file():
        return ()
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("schema") == SCHEMA:
            values.append(item)
    return tuple(values)


def attempt_count(root: Path, work: str, tier: str) -> int:
    return sum(1 for item in load_events(root, work) if item.get("event") == "attempt" and item.get("tier") == tier)


def core_budgets(workspace: Any, swarm: str, work: str) -> tuple[Budget, ...]:
    summarize = getattr(workspace, "summarize_usage", None)
    if not callable(summarize):
        return ()
    try:
        summary = summarize(swarm, work)
    except (OSError, RuntimeError, ValueError, FileNotFoundError):
        return ()
    if not getattr(summary, "budget_limits", None):
        return ()
    return (budget_from_core(summary, scope=f"work:{swarm}/{work}"),)


def core_usage_snapshot(workspace: Any, swarm: str, work: str) -> dict[str, Any] | None:
    summarize = getattr(workspace, "summarize_usage", None)
    if not callable(summarize):
        return None
    try:
        summary = summarize(swarm, work)
    except (OSError, RuntimeError, ValueError, FileNotFoundError):
        return None
    consumed = dict(getattr(summary, "consumed", {}) or {})
    measurement = dict(getattr(summary, "consumed_measurement", {}) or {})
    return {
        "consumed": consumed,
        "measurement": measurement,
        "budget_limits": dict(getattr(summary, "budget_limits", {}) or {}) or None,
        "remaining": dict(getattr(summary, "remaining", {}) or {}) or None,
    }


def record_executor_event(
    root: Path,
    *,
    event: str,
    work: str,
    swarm: str,
    runtime: Any,
    plan: Any | None = None,
    tier: str | None = None,
    model: str | None = None,
    workspace: Any | None = None,
    reason: str | None = None,
    exit_code: int | None = None,
) -> str | None:
    """Record one effective executor event without making telemetry authoritative.

    The runtime plan is preferred because it contains the provider-neutral binding
    and the economic tier chosen by cheap-first routing. Explicit/legacy launches
    that have no tier are retained as unknown by the summary instead of being
    silently omitted. Telemetry failures never block governed execution.
    """

    binding = getattr(plan, "binding", None)
    agent_ref = getattr(binding, "agent", None)
    model_ref = getattr(binding, "model", None)
    agent = getattr(agent_ref, "id", None) or getattr(runtime, "id", None)
    resolved_model = getattr(model_ref, "model", None) or model
    resolved_tier = tier or getattr(plan, "execution_tier", None)
    usage = core_usage_snapshot(workspace, swarm, work) if workspace is not None else None
    try:
        return record_event(
            root,
            EconomicsEvent(
                event,
                work,
                resolved_tier,
                agent,
                resolved_model,
                purpose="executor",
                reason=reason,
                exit_code=exit_code,
                core_usage=usage,
            ),
        )
    except OSError:
        return None


def summarize_economics(root: Path, work: str) -> dict[str, Any]:
    events = load_events(root, work)
    attempts: dict[str, int] = {}
    successes: dict[str, int] = {}
    failures: dict[str, int] = {}
    escalations = 0
    unaccounted_paid_usage = 0
    for item in events:
        tier = str(item.get("tier") or "unknown")
        if item.get("event") == "attempt":
            attempts[tier] = attempts.get(tier, 0) + 1
        elif item.get("event") == "success":
            successes[tier] = successes.get(tier, 0) + 1
        elif item.get("event") == "failure":
            failures[tier] = failures.get(tier, 0) + 1
        elif item.get("event") == "escalation":
            escalations += 1
        elif item.get("event") == "planner-usage-unaccounted":
            unaccounted_paid_usage += 1
    return {
        "schema": SCHEMA,
        "work": work,
        "attempts": dict(sorted(attempts.items())),
        "successes": dict(sorted(successes.items())),
        "failures": dict(sorted(failures.items())),
        "escalations": escalations,
        "unaccounted_paid_usage": unaccounted_paid_usage,
        "events": len(events),
    }
