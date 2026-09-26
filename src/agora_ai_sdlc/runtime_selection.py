"""Explainable runtime routing, budgets and governed fallback decisions."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from agora_ai_sdlc.agent_capabilities import CAPABILITY_IDS, CapabilityError, manifest_for
from agora_ai_sdlc.execution_requirements import ExecutionRequirements
from agora_ai_sdlc.runtime_domain import (
    ModelRuntimeRef,
    RuntimeBinding,
    RuntimeNormalizationError,
    normalize_runtime,
)

SCHEMA = "agora-ai-sdlc/runtime-selection/v1"
# `capability-mismatch` is opt-in: it is never part of the default allowed fallback signals.
FALLBACK_SIGNALS = (
    "quota",
    "runtime-unavailable",
    "budget-exhausted",
    "budget-unavailable",
    "capability-mismatch",
)
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
    """Legacy flat runtime (v1); `binding` is its deterministic v2 normalization."""

    id: str
    integration: str
    provider: str
    model: str

    @property
    def binding(self) -> RuntimeBinding:
        return normalize_runtime(
            {"id": self.id, "integration": self.integration, "provider": self.provider, "model": self.model}
        )


@dataclass(frozen=True)
class Candidate:
    runtime: RuntimeRef | RuntimeBinding | ModelRuntimeRef
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
    ids = [_runtime_id(candidate.runtime) for candidate in route.candidates]
    if any(not runtime_id.strip() for runtime_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("runtime candidate ids must be non-empty and unique")
    for candidate in route.candidates:
        if isinstance(candidate.runtime, (RuntimeBinding, ModelRuntimeRef)):
            continue
        if any(
            not value.strip()
            for value in (candidate.runtime.integration, candidate.runtime.provider, candidate.runtime.model)
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


def _runtime_id(runtime: RuntimeRef | RuntimeBinding | ModelRuntimeRef) -> str:
    return runtime.agent.id if isinstance(runtime, RuntimeBinding) else runtime.id


def _runtime_dict(runtime: RuntimeRef | RuntimeBinding) -> dict:
    binding = runtime if isinstance(runtime, RuntimeBinding) else runtime.binding
    return {**binding.to_legacy(), "binding": binding.to_dict()}


AVAILABILITY_BLOCKERS = ("runtime.integration_unavailable", "runtime.model_unavailable")


def _binding_of(runtime: RuntimeRef | RuntimeBinding | ModelRuntimeRef) -> RuntimeBinding | None:
    """Binding for an agent candidate; a model runtime alone (or unsafe legacy data) has none."""
    if isinstance(runtime, ModelRuntimeRef):
        return None
    if isinstance(runtime, RuntimeBinding):
        return runtime
    try:
        return runtime.binding
    except RuntimeNormalizationError:
        return None


def _admission_blockers(
    candidate: Candidate,
    requirements: ExecutionRequirements,
    availability: Mapping[str, Any] | None,
) -> tuple[list[dict], list[str]]:
    """Availability, capability and model-binding blockers; static manifests never read observations."""
    binding = _binding_of(candidate.runtime)
    if binding is None:
        return [_blocker("runtime.agent_required", "runtime is not an agent host and cannot execute the action")], []
    blockers: list[dict] = []
    if availability is not None:
        agent = availability.get(binding.agent.id)
        if agent is None or not (agent.installed and agent.responsive):
            blockers.append(
                _blocker("runtime.integration_unavailable", "agent runtime is not installed and responsive")
            )
        model = binding.model and availability.get(binding.model.id)
        if model and not (model.installed and model.responsive and model.service in (None, "responsive")):
            blockers.append(_blocker("runtime.model_unavailable", "model runtime is not installed and responsive"))
    missing: list[str] = []
    try:
        manifest = manifest_for(binding.agent)
    except CapabilityError as error:
        blockers.append(_blocker("runtime.agent_unknown", str(error), agent_code=error.code))
        return blockers, missing
    needed = set(requirements.required_capabilities)
    if binding.model is not None:
        needed.add("model_selection")
    missing = [name for name in CAPABILITY_IDS if name in needed and not manifest.supports(name)]
    if missing:
        blockers.append(
            _blocker("runtime.capability_missing", "agent runtime lacks required capabilities", missing=tuple(missing))
        )
    if requirements.reasoning_tier == "local" and binding.model is None:
        blockers.append(_blocker("runtime.model_binding_missing", "local reasoning requires an explicit model binding"))
    return blockers, missing


def admit_binding(
    binding: RuntimeBinding,
    requirements: ExecutionRequirements,
    availability: Mapping[str, Any] | None = None,
) -> tuple[dict, ...]:
    """Public admission check for one binding; an empty result means admissible."""
    blockers, _ = _admission_blockers(Candidate(binding, {}, {}, {}), requirements, availability)
    return tuple(blockers)


def _admission_signal(blockers: list[dict]) -> str:
    codes = {blocker["code"] for blocker in blockers}
    return "runtime-unavailable" if codes & set(AVAILABILITY_BLOCKERS) else "capability-mismatch"


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
    requirements: ExecutionRequirements | None = None,
    availability: Mapping[str, Any] | None = None,
) -> dict:
    """Select from explicit order using Core facts, never provider output or opaque scoring.

    With `requirements`, each candidate must also be admitted: availability, agent capabilities
    and model binding are proven deterministically before an executor can launch.
    """
    _validate(route, budgets, signal)
    unknown_capabilities = sorted(set(requirements.required_capabilities) - set(CAPABILITY_IDS)) if requirements else []
    if unknown_capabilities:
        raise ValueError(f"unknown capability ids in requirements: {unknown_capabilities}")
    consumed = _consumed(budgets)
    if requirements is not None and requirements.human_authority_required:
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
                    "runtime.human_authority_required", "no agent runtime can satisfy a human authority requirement"
                ),
            ),
        }
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
        current = current_runtime or _runtime_id(route.candidates[0].runtime)
        matches = [
            index for index, candidate in enumerate(route.candidates) if _runtime_id(candidate.runtime) == current
        ]
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
        admission_blockers: list[dict] = []
        missing: list[str] = []
        if requirements is not None:
            admission_blockers, missing = _admission_blockers(candidate, requirements, availability)
        blockers = [*policy_blockers, *budget_blockers, *admission_blockers]
        entry = {
            "runtime": _runtime_id(candidate.runtime),
            "blockers": tuple(blocker["code"] for blocker in blockers),
        }
        if requirements is not None:
            entry["missing_capabilities"] = tuple(missing)
        considered.append(entry)
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
            if budget_blockers:
                fallback_reason = (
                    "budget-exhausted"
                    if any(blocker["code"] == "budget.exhausted" for blocker in budget_blockers)
                    else "budget-unavailable"
                )
            else:
                fallback_reason = _admission_signal(admission_blockers)
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
