"""Cost-aware runtime pools for cheap-first executor selection.

The pool is project configuration. Laya and Core remain provider-neutral:
Laya supplies reasoning requirements, Core supplies authority, and this module
orders explicitly configured runtime bindings by economic tier before handing
them to the existing deterministic runtime selector.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agora_ai_sdlc.execution_economics import attempt_count
from agora_ai_sdlc.execution_policy import EXECUTION_TIERS, ExecutionPolicy, execution_policy_for, tier_rank
from agora_ai_sdlc.execution_requirements import ExecutionRequirements
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding, normalize_runtime
from agora_ai_sdlc.runtime_selection import Budget, Candidate, Route, select_runtime

ALLOW = {"allowed": True, "blockers": []}
_FALLBACKS = ("quota", "runtime-unavailable", "budget-exhausted", "budget-unavailable", "capability-mismatch")
_INTEGRATIONS = {"claude": "claude-code", "codex": "codex", "opencode": "opencode"}
_DEFAULT_PROVIDERS = {"claude": "anthropic", "codex": "openai"}


class RuntimePoolError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class PoolCandidate:
    tier: str
    binding: RuntimeBinding
    order: int
    activities: tuple[str, ...] = ()
    projected_usage: dict[str, int | None] | None = None

    def applies_to(self, activity: str) -> bool:
        return not self.activities or activity in self.activities


@dataclass(frozen=True)
class RuntimePool:
    profile: str
    allow_paid_auto: bool
    allow_frontier_auto: bool
    call_budgets: dict[str, int]
    retry_limits: dict[str, int]
    candidates: tuple[PoolCandidate, ...]


@dataclass(frozen=True)
class PoolSelection:
    binding: RuntimeBinding
    tier: str
    reason: str
    decision: dict


def _project_payload(root: Path) -> dict[str, Any]:
    path = root / "ai-sdlc" / "project.yaml"
    if not path.is_file():
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def _binding(entry: dict[str, Any]) -> RuntimeBinding:
    runtime = entry.get("runtime")
    if isinstance(runtime, dict):
        return normalize_runtime(runtime)

    agent_value = entry.get("agent")
    if isinstance(agent_value, dict):
        agent_id = str(agent_value.get("id") or "").strip()
        integration = str(agent_value.get("integration") or "").strip()
    else:
        agent_id = str(agent_value or "").strip()
        integration = _INTEGRATIONS.get(agent_id, agent_id)
    if not agent_id or not integration:
        raise RuntimePoolError("routing.agent", "routing candidate requires an agent runtime")

    model_value = entry.get("model")
    if model_value is None:
        provider = _DEFAULT_PROVIDERS.get(agent_id)
        if provider is None:
            return RuntimeBinding(AgentRuntimeRef(agent_id, integration))
        return RuntimeBinding(
            AgentRuntimeRef(agent_id, integration),
            ModelRuntimeRef(provider, provider, "configured-default"),
        )

    if isinstance(model_value, dict):
        provider = str(model_value.get("provider") or "").strip()
        model = str(model_value.get("model") or "").strip()
        model_id = str(model_value.get("id") or provider).strip()
    elif isinstance(model_value, str):
        raw = model_value.strip()
        if "/" in raw:
            provider, model = raw.split("/", 1)
        else:
            provider = _DEFAULT_PROVIDERS.get(agent_id, "")
            model = raw
        model_id = provider
    else:
        raise RuntimePoolError("routing.model", "routing candidate model must be text or a mapping")

    if not provider or not model:
        raise RuntimePoolError(
            "routing.model",
            f"routing candidate for {agent_id!r} requires provider/model or an explicit model mapping",
        )
    return RuntimeBinding(
        AgentRuntimeRef(agent_id, integration),
        ModelRuntimeRef(model_id, provider, model),
    )


def load_runtime_pool(root: Path) -> RuntimePool | None:
    routing = _project_payload(root).get("routing")
    if not isinstance(routing, dict) or routing.get("profile") != "cheap-first":
        return None
    raw_candidates = routing.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise RuntimePoolError("routing.candidates", "cheap-first routing requires at least one candidate")

    candidates: list[PoolCandidate] = []
    for order, value in enumerate(raw_candidates):
        if not isinstance(value, dict):
            raise RuntimePoolError("routing.candidate", "routing candidates must be mappings")
        tier = str(value.get("tier") or "").strip()
        if tier not in EXECUTION_TIERS:
            raise RuntimePoolError("routing.tier", f"unknown routing tier {tier!r}")
        activities_value = value.get("activities") or ()
        if not isinstance(activities_value, (list, tuple)) or any(
            not isinstance(item, str) or not item.strip() for item in activities_value
        ):
            raise RuntimePoolError("routing.activities", "candidate activities must be a string list")
        usage = value.get("projected_usage")
        if usage is not None and (
            not isinstance(usage, dict)
            or any(
                not isinstance(name, str)
                or not name
                or (amount is not None and (not isinstance(amount, int) or isinstance(amount, bool) or amount < 0))
                for name, amount in usage.items()
            )
        ):
            raise RuntimePoolError("routing.projected_usage", "projected usage must contain non-negative integers")
        candidates.append(
            PoolCandidate(
                tier=tier,
                binding=_binding(value),
                order=order,
                activities=tuple(activities_value),
                projected_usage=dict(usage or {}),
            )
        )

    raw_call_budgets = routing.get("call_budgets") or {}
    if not isinstance(raw_call_budgets, dict) or any(
        tier not in EXECUTION_TIERS
        or not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 0
        for tier, limit in raw_call_budgets.items()
    ):
        raise RuntimePoolError(
            "routing.call_budgets",
            "call_budgets must map known execution tiers to non-negative integer limits",
        )

    raw_retry_limits = routing.get("retry_limits") or {"local": 2, "free": 2}
    if not isinstance(raw_retry_limits, dict) or any(
        tier not in EXECUTION_TIERS
        or not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 0
        for tier, limit in raw_retry_limits.items()
    ):
        raise RuntimePoolError(
            "routing.retry_limits",
            "retry_limits must map known execution tiers to non-negative integer limits",
        )

    return RuntimePool(
        profile="cheap-first",
        allow_paid_auto=bool(routing.get("allow_paid_auto", False)),
        allow_frontier_auto=bool(routing.get("allow_frontier_auto", False)),
        call_budgets=dict(raw_call_budgets),
        retry_limits=dict(raw_retry_limits),
        candidates=tuple(candidates),
    )


def retry_limit_for(root: Path, tier: str | None) -> int:
    if tier is None:
        return 0
    pool = load_runtime_pool(root)
    if pool is None:
        return 0
    return int(pool.retry_limits.get(tier, 0))


def _candidate_id(binding: RuntimeBinding) -> str:
    if binding.model is None:
        return binding.agent.id
    return f"{binding.agent.id}+{binding.model.provider}/{binding.model.model}"


def _eligible(
    pool: RuntimePool,
    policy: ExecutionPolicy,
    activity: str,
    *,
    root: Path,
    work_id: str | None,
    minimum_tier: str | None,
    maximum_tier: str | None,
    allowed_agents: tuple[str, ...] | None,
) -> tuple[PoolCandidate, ...]:
    values = []
    lower = tier_rank(minimum_tier) if minimum_tier is not None else 0
    upper = tier_rank(maximum_tier) if maximum_tier is not None else tier_rank(policy.max_automatic_tier)
    upper = min(upper, tier_rank(policy.max_automatic_tier))
    for candidate in pool.candidates:
        rank = tier_rank(candidate.tier)
        if rank < lower or rank > upper:
            continue
        if allowed_agents is not None and candidate.binding.agent.id not in allowed_agents:
            continue
        if not candidate.applies_to(activity) or not policy.allows(candidate.tier):
            continue
        if rank >= tier_rank("paid-efficient") and not pool.allow_paid_auto:
            continue
        if candidate.tier == "frontier" and not pool.allow_frontier_auto:
            continue
        limit = pool.call_budgets.get(candidate.tier)
        if work_id is not None and limit is not None and attempt_count(root, work_id, candidate.tier) >= limit:
            continue
        values.append(candidate)
    return tuple(sorted(values, key=lambda item: (tier_rank(item.tier), item.order)))


def select_from_runtime_pool(
    root: Path,
    requirements: ExecutionRequirements,
    *,
    availability: dict[str, RuntimeDiscovery] | None = None,
    budgets: tuple[Budget, ...] = (),
    work_id: str | None = None,
    minimum_tier: str | None = None,
    maximum_tier: str | None = None,
    allowed_agents: tuple[str, ...] | None = None,
) -> PoolSelection | None:
    """Return the cheapest admissible configured binding, or None when routing is not configured."""

    pool = load_runtime_pool(root)
    if pool is None:
        return None
    policy = execution_policy_for(requirements)
    candidates = _eligible(
        pool,
        policy,
        requirements.activity_class,
        root=root,
        work_id=work_id,
        minimum_tier=minimum_tier,
        maximum_tier=maximum_tier,
        allowed_agents=allowed_agents,
    )
    if not candidates:
        raise RuntimePoolError(
            "routing.no_candidate",
            f"no automatic candidate is permitted for {requirements.activity_class}/{requirements.reasoning_tier}",
        )

    observed = availability
    if observed is None:
        observed = {item.id: item for item in discover_runtimes(root)}
    route = Route(
        requirements.activity_class,
        tuple(
            Candidate(
                runtime=item.binding,
                projected_usage=dict(item.projected_usage or {}),
                data_policy=ALLOW,
                review_policy=ALLOW,
            )
            for item in candidates
        ),
        allowed_fallback_signals=_FALLBACKS,
    )
    decision = select_runtime(route, requirements=requirements, availability=observed, budgets=budgets)
    if not decision["allowed"] or decision["selected"] is None:
        codes = ",".join(blocker["code"] for blocker in decision.get("blockers", ())) or "no-eligible-candidate"
        raise RuntimePoolError("routing.blocked", f"cost-aware runtime selection is blocked: {codes}")

    binding = normalize_runtime(decision["selected"]["binding"])
    selected_id = _candidate_id(binding)
    selected = next((item for item in candidates if _candidate_id(item.binding) == selected_id), None)
    if selected is None:
        raise RuntimePoolError("routing.selection", "selected runtime is not present in the configured pool")
    return PoolSelection(
        binding=binding,
        tier=selected.tier,
        reason=str(decision.get("selection_reason") or "configured cheap-first preference"),
        decision=decision,
    )
