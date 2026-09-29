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
    measurement: dict[str, Any] | None = None
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



def record_decision_event(
    root: Path,
    *,
    work: str,
    route: str,
    reason: str,
    generative_call: bool,
    tier: str | None = None,
    measurement: dict[str, Any] | None = None,
) -> str | None:
    """Record an observed routing decision without inventing a counterfactual cost."""

    try:
        return record_event(
            root,
            EconomicsEvent(
                "decision",
                work,
                tier,
                None,
                None,
                purpose="decision",
                reason=reason,
                measurement={
                    "source": "observed",
                    "route": route,
                    "generative_call": generative_call,
                    **(measurement or {}),
                },
            ),
        )
    except OSError:
        return None


def record_context_event(
    root: Path,
    *,
    work: str,
    before: int,
    after: int,
    basis: str,
    reason: str = "bounded-context-selection",
) -> str | None:
    """Record context reduction with an explicit measurement basis."""

    if before < 0 or after < 0:
        raise ValueError("context measurements must be non-negative")
    if basis not in {"estimated_tokens", "characters", "bytes", "provider_reported_tokens"}:
        raise ValueError(f"unsupported context measurement basis: {basis}")
    try:
        return record_event(
            root,
            EconomicsEvent(
                "context",
                work,
                None,
                None,
                None,
                purpose="context",
                reason=reason,
                measurement={
                    "source": "observed"
                    if basis in {"characters", "bytes", "provider_reported_tokens"}
                    else "estimated",
                    "basis": basis,
                    "before": before,
                    "after": after,
                    "reduction": max(0, before - after),
                },
            ),
        )
    except OSError:
        return None

def summarize_economics(root: Path, work: str) -> dict[str, Any]:
    events = load_events(root, work)
    attempts: dict[str, int] = {}
    successes: dict[str, int] = {}
    failures: dict[str, int] = {}
    routes: dict[tuple[str, str, str, str], dict[str, int]] = {}
    decisions: dict[str, int] = {}
    generative_calls = 0
    generative_calls_avoided = 0
    avoidance_reasons: dict[str, int] = {}
    context_measurements: list[dict[str, Any]] = []
    provider_input_tokens = 0
    provider_output_tokens = 0
    provider_usage_events = 0
    escalations = 0
    unaccounted_paid_usage = 0
    for item in events:
        tier = str(item.get("tier") or "unknown")
        event = item.get("event")
        if event in {"attempt", "success", "failure"}:
            measurement = item.get("measurement")
            provider_usage = measurement.get("provider_usage") if isinstance(measurement, dict) else None
            if (
                event in {"success", "failure"}
                and isinstance(provider_usage, dict)
                and provider_usage.get("basis") == "provider_reported_tokens"
                and isinstance(provider_usage.get("input_tokens"), int)
                and not isinstance(provider_usage.get("input_tokens"), bool)
                and provider_usage["input_tokens"] >= 0
                and isinstance(provider_usage.get("output_tokens"), int)
                and not isinstance(provider_usage.get("output_tokens"), bool)
                and provider_usage["output_tokens"] >= 0
            ):
                provider_input_tokens += provider_usage["input_tokens"]
                provider_output_tokens += provider_usage["output_tokens"]
                provider_usage_events += 1
            key = (
                tier,
                str(item.get("purpose") or "unknown"),
                str(item.get("agent") or "unknown"),
                str(item.get("model") or "unknown"),
            )
            route = routes.setdefault(key, {"attempts": 0, "successes": 0, "failures": 0})
            route[{"attempt": "attempts", "success": "successes", "failure": "failures"}[event]] += 1
        if event == "attempt":
            attempts[tier] = attempts.get(tier, 0) + 1
        elif event == "success":
            successes[tier] = successes.get(tier, 0) + 1
        elif event == "failure":
            failures[tier] = failures.get(tier, 0) + 1
        elif event == "decision":
            measurement = item.get("measurement")
            if isinstance(measurement, dict):
                route_name = str(measurement.get("route") or "unknown")
                decisions[route_name] = decisions.get(route_name, 0) + 1
                if measurement.get("generative_call") is True:
                    generative_calls += 1
                elif measurement.get("generative_call") is False and measurement.get("call_avoided") is True:
                    generative_calls_avoided += 1
                    avoidance_reason = str(measurement.get("avoidance_reason") or item.get("reason") or "unknown")
                    avoidance_reasons[avoidance_reason] = avoidance_reasons.get(avoidance_reason, 0) + 1
        elif event == "context":
            measurement = item.get("measurement")
            if isinstance(measurement, dict):
                context_measurements.append(dict(measurement))
        elif event == "escalation":
            escalations += 1
        elif event == "planner-usage-unaccounted":
            unaccounted_paid_usage += 1
    route_summary = [
        {
            "tier": tier,
            "purpose": purpose,
            "agent": agent,
            "model": model,
            **counts,
        }
        for (tier, purpose, agent, model), counts in sorted(routes.items())
    ]
    return {
        "schema": SCHEMA,
        "work": work,
        "attempts": dict(sorted(attempts.items())),
        "successes": dict(sorted(successes.items())),
        "failures": dict(sorted(failures.items())),
        "routes": route_summary,
        "decisions": dict(sorted(decisions.items())),
        "generative_calls_observed": generative_calls,
        "provider_usage": (
            {
                "basis": "provider_reported_tokens",
                "input_tokens": provider_input_tokens,
                "output_tokens": provider_output_tokens,
                "total_tokens": provider_input_tokens + provider_output_tokens,
                "events": provider_usage_events,
            }
            if provider_usage_events
            else None
        ),
        "generative_calls_avoided": generative_calls_avoided,
        "avoidance_reasons": dict(sorted(avoidance_reasons.items())),
        "context_measurements": context_measurements,
        "escalations": escalations,
        "unaccounted_paid_usage": unaccounted_paid_usage,
        "events": len(events),
    }



def render_economics(root: Path, work: str) -> str:
    """Render a compact economics summary without inventing unknown cost/token data."""

    summary = summarize_economics(root, work)
    from agora_ai_sdlc.amplification import amplification_report, measurement_from_economics

    amplification = amplification_report(root, work, measurement_from_economics(summary))
    lines = [
        "Agora Flow | Economics",
        "",
        f"Work: {work}",
        f"Observed generative calls: {summary['generative_calls_observed']}",
        f"Observed generative calls avoided: {summary['generative_calls_avoided']}",
        (
            f"Provider tokens: {summary['provider_usage']['total_tokens']} "
            f"(input={summary['provider_usage']['input_tokens']}, "
            f"output={summary['provider_usage']['output_tokens']})"
            if summary["provider_usage"]
            else "Provider tokens: unknown"
        ),
        (
            f"LLM Amplification Factor: {amplification.factor:.4f}"
            if amplification.comparable and amplification.factor is not None
            else f"LLM Amplification Factor: unknown ({amplification.reason})"
        ),
    ]
    decisions = summary["decisions"]
    if decisions:
        lines.append("Decision routes:")
        for route, count in decisions.items():
            lines.append(f"  - {route}: {count}")

    attempts = summary["attempts"]
    if attempts:
        lines.append("Execution attempts:")
        for tier, count in attempts.items():
            lines.append(f"  - {tier}: {count}")

    measurements = summary["context_measurements"]
    if measurements:
        lines.append("Context measurements:")
        for measurement in measurements:
            basis = measurement.get("basis", "unknown")
            source = measurement.get("source", "unknown")
            before = measurement.get("before")
            after = measurement.get("after")
            reduction = measurement.get("reduction")
            lines.append(
                f"  - {before} -> {after}; reduction={reduction}; basis={basis}; source={source}"
            )

    if summary["unaccounted_paid_usage"]:
        lines.append(
            f"Unaccounted paid usage events: {summary['unaccounted_paid_usage']} "
            "(cost remains unknown)"
        )
    lines.append("")
    lines.append("No counterfactual token or monetary savings are claimed without a measured baseline.")
    return "\n".join(lines)
