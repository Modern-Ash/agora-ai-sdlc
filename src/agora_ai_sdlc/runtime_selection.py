"""Explainable runtime routing, budgets and governed fallback decisions."""

from dataclasses import dataclass, field
from typing import Protocol

SCHEMA = "agora-ai-sdlc/runtime-selection/v1"
FALLBACK_SIGNALS = ("quota", "runtime-unavailable", "budget-exhausted", "budget-unavailable")
FAILURE_SIGNALS = (*FALLBACK_SIGNALS, "ordinary-failure")
MEASUREMENTS = ("measured", "provider-reported", "unknown")


class CoreUsageSummary(Protocol):
    budget_limits: dict[str, int] | None
    consumed: dict[str, int]
    records: int
    # Agora Core >=0.9.1: weakest measurement basis per consumed dimension (absent on older Core).
    consumed_measurement: dict[str, str]


@dataclass(frozen=True)
class RuntimeRef:
    id: str
    integration: str
    provider: str
    model: str


@dataclass(frozen=True)
class Candidate:
    runtime: RuntimeRef
    projected_usage: dict[str, int | None]
    data_policy: dict
    review_policy: dict


@dataclass(frozen=True)
class Route:
    activity_class: str
    candidates: tuple[Candidate, ...]
    allowed_fallback_signals: tuple[str, ...] = (
        "quota",
        "runtime-unavailable",
        "budget-exhausted",
    )


@dataclass(frozen=True)
class Budget:
    scope: str
    limits: dict[str, int]
    consumed: dict[str, int | None]
    # How each consumed amount was obtained; a missing dimension is `unknown`, never `measured`.
    measurement: dict[str, str] = field(default_factory=dict)


def budget_from_core(summary: CoreUsageSummary, *, scope: str) -> Budget:
    """Use Core's durable usage summary; an absent budget means no limits."""
    limits = dict(summary.budget_limits or {})
    consumed = {dimension: summary.consumed.get(dimension) if summary.records else 0 for dimension in limits}
    reported = getattr(summary, "consumed_measurement", None) or {}
    measurement = {
        dimension: reported.get(dimension, "unknown") if summary.records else "unknown" for dimension in limits
    }
    return Budget(scope=scope, limits=limits, consumed=consumed, measurement=measurement)


def _blocker(code: str, message: str, **fields) -> dict:
    return {"code": code, "message": message, **fields}


def _validate(route: Route, budgets: tuple[Budget, ...], signal: str | None) -> None:
    if not route.activity_class.strip():
        raise ValueError("activity class is required")
    if not route.candidates:
        raise ValueError("route requires at least one runtime candidate")
    ids = [candidate.runtime.id for candidate in route.candidates]
    if any(not runtime_id.strip() for runtime_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("runtime candidate ids must be non-empty and unique")
    if any(
        not value.strip()
        for candidate in route.candidates
        for value in (
            candidate.runtime.integration,
            candidate.runtime.provider,
            candidate.runtime.model,
        )
    ):
        raise ValueError("runtime integration, provider and model are required")
    if signal is not None and signal not in FAILURE_SIGNALS:
        raise ValueError(f"unsupported Core failure signal: {signal}")
    if any(item not in FALLBACK_SIGNALS for item in route.allowed_fallback_signals):
        raise ValueError("route contains an unsupported fallback signal")
    scopes = [budget.scope for budget in budgets]
    if len(scopes) != len(set(scopes)):
        raise ValueError("budget scopes must be unique")
    for budget in budgets:
        if not budget.scope.strip():
            raise ValueError("budget scope is required")
        for dimension, limit in budget.limits.items():
            if not dimension.strip() or not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
                raise ValueError("budget limits require named non-negative integer dimensions")
        for amount in budget.consumed.values():
            if amount is not None and (not isinstance(amount, int) or isinstance(amount, bool) or amount < 0):
                raise ValueError("consumed budget amounts must be non-negative integers or unavailable")
        if any(basis not in MEASUREMENTS for basis in budget.measurement.values()):
            raise ValueError("consumed budget measurement must be measured, provider-reported or unknown")
    for candidate in route.candidates:
        for amount in candidate.projected_usage.values():
            if amount is not None and (not isinstance(amount, int) or isinstance(amount, bool) or amount < 0):
                raise ValueError("projected usage must be non-negative integers or unavailable")


def _policy_blockers(candidate: Candidate) -> list[dict]:
    blockers = []
    for name, decision in (("data", candidate.data_policy), ("review", candidate.review_policy)):
        if decision.get("allowed") is not True:
            blockers.append(
                _blocker(
                    f"runtime.{name}_policy",
                    f"runtime does not satisfy {name} policy",
                    policy_blockers=tuple(item.get("code", "unknown") for item in decision.get("blockers", [])),
                )
            )
    return blockers


def _budget_blockers(candidate: Candidate, budgets: tuple[Budget, ...]) -> list[dict]:
    blockers = []
    for budget in budgets:
        for dimension, limit in sorted(budget.limits.items()):
            consumed = budget.consumed.get(dimension)
            projected = candidate.projected_usage.get(dimension)
            if consumed is None or projected is None:
                blockers.append(
                    _blocker(
                        "budget.unavailable",
                        f"{dimension} usage is unavailable for budget scope {budget.scope}",
                        scope=budget.scope,
                        dimension=dimension,
                    )
                )
            elif consumed + projected > limit:
                blockers.append(
                    _blocker(
                        "budget.exhausted",
                        f"{dimension} budget is exhausted for scope {budget.scope}",
                        scope=budget.scope,
                        dimension=dimension,
                    )
                )
    return blockers


def _runtime_dict(runtime: RuntimeRef) -> dict[str, str]:
    return {
        "id": runtime.id,
        "integration": runtime.integration,
        "provider": runtime.provider,
        "model": runtime.model,
    }


def _consumed(budgets: tuple[Budget, ...]) -> dict[str, dict[str, int | None]]:
    return {budget.scope: dict(sorted(budget.consumed.items())) for budget in budgets}


def _measurement(budgets: tuple[Budget, ...]) -> dict[str, dict[str, str]]:
    """Per scope and dimension; anything not explicitly measured or provider-reported is unknown."""
    return {
        budget.scope: {dimension: budget.measurement.get(dimension, "unknown") for dimension in sorted(budget.consumed)}
        for budget in budgets
    }


def select_runtime(
    route: Route,
    *,
    budgets: tuple[Budget, ...] = (),
    signal: str | None = None,
    current_runtime: str | None = None,
) -> dict:
    """Select from explicit order using Core facts, never provider output or opaque scoring."""
    _validate(route, budgets, signal)
    consumed = _consumed(budgets)
    if signal == "ordinary-failure":
        return {
            "schema": SCHEMA,
            "allowed": False,
            "activity_class": route.activity_class,
            "selected": None,
            "selection_reason": None,
            "fallback": {"used": False, "reason": None},
            "consumed_budget": consumed,
            "consumed_measurement": _measurement(budgets),
            "considered": (),
            "blockers": (
                _blocker(
                    "fallback.ordinary_failure",
                    "ordinary task failure cannot change runtime or provider",
                ),
            ),
        }

    start = 0
    fallback_reason = None
    if signal is not None:
        if signal not in route.allowed_fallback_signals:
            return _blocked_signal(route, budgets, signal)
        current = current_runtime or route.candidates[0].runtime.id
        matches = [index for index, candidate in enumerate(route.candidates) if candidate.runtime.id == current]
        if not matches:
            raise ValueError(f"current runtime {current!r} is not in the configured route")
        start = matches[0] + 1
        fallback_reason = signal

    considered: list[dict] = []
    terminal_blockers: tuple[dict, ...] | None = None
    for index in range(start, len(route.candidates)):
        candidate = route.candidates[index]
        policy_blockers = _policy_blockers(candidate)
        budget_blockers = _budget_blockers(candidate, budgets)
        blockers = [*policy_blockers, *budget_blockers]
        considered.append(
            {
                "runtime": candidate.runtime.id,
                "blockers": tuple(blocker["code"] for blocker in blockers),
            }
        )
        if not blockers:
            used_fallback = index > 0
            return {
                "schema": SCHEMA,
                "allowed": True,
                "activity_class": route.activity_class,
                "selected": _runtime_dict(candidate.runtime),
                "selection_reason": (
                    f"configured preference for {route.activity_class}"
                    if not used_fallback
                    else f"authorized fallback after {fallback_reason}"
                ),
                "fallback": {"used": used_fallback, "reason": fallback_reason},
                "consumed_budget": consumed,
                "consumed_measurement": _measurement(budgets),
                "considered": tuple(considered),
                "blockers": (),
            }
        if index == 0 and signal is None:
            if policy_blockers:
                break
            fallback_reason = (
                "budget-exhausted"
                if any(blocker["code"] == "budget.exhausted" for blocker in budget_blockers)
                else "budget-unavailable"
            )
            if fallback_reason not in route.allowed_fallback_signals:
                terminal_blockers = (
                    _blocker(
                        "fallback.unauthorized_signal",
                        f"fallback is not authorized for policy signal {fallback_reason}",
                    ),
                )
                break

    blockers = terminal_blockers or (
        _blocker("runtime.no_eligible_candidate", "no configured runtime candidate satisfies policy and budget"),
    )
    return {
        "schema": SCHEMA,
        "allowed": False,
        "activity_class": route.activity_class,
        "selected": None,
        "selection_reason": None,
        "fallback": {"used": False, "reason": fallback_reason},
        "consumed_budget": consumed,
        "consumed_measurement": _measurement(budgets),
        "considered": tuple(considered),
        "blockers": blockers,
    }


def _blocked_signal(route: Route, budgets: tuple[Budget, ...], signal: str) -> dict:
    return {
        "schema": SCHEMA,
        "allowed": False,
        "activity_class": route.activity_class,
        "selected": None,
        "selection_reason": None,
        "fallback": {"used": False, "reason": signal},
        "consumed_budget": _consumed(budgets),
        "consumed_measurement": _measurement(budgets),
        "considered": (),
        "blockers": (_blocker("fallback.unauthorized_signal", f"fallback is not authorized for Core signal {signal}"),),
    }
