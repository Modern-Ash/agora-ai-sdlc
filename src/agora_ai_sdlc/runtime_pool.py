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

from agora_ai_sdlc.economic_telemetry import summarize_economics
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
    purposes: tuple[str, ...] = ("executor", "planner", "reviewer")
    projected_usage: dict[str, int | None] | None = None

    def applies_to(self, activity: str, purpose: str) -> bool:
        return (not self.activities or activity in self.activities) and purpose in self.purposes


@dataclass(frozen=True)
class RuntimePool:
    profile: str
    allow_paid_auto: bool
    allow_frontier_auto: bool
    tier_call_limits: dict[str, int]
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
        purposes_value = value.get("purposes") or ("executor", "planner", "reviewer")
        if not isinstance(purposes_value, (list, tuple)) or any(
            item not in {"executor", "planner", "reviewer"} for item in purposes_value
        ):
            raise RuntimePoolError(
                "routing.purposes",
                "candidate purposes must contain executor, planner and/or reviewer",
            )
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
                purposes=tuple(purposes_value),
                projected_usage=dict(usage or {}),
            )
        )

    limits_value = routing.get("tier_call_limits") or {}
    if not isinstance(limits_value, dict) or any(
        tier not in EXECUTION_TIERS or not isinstance(limit, int) or isinstance(limit, bool) or limit < 0
        for tier, limit in limits_value.items()
    ):
        raise RuntimePoolError(
            "routing.tier_call_limits",
            "tier call limits must map known tiers to non-negative integers",
        )
    return RuntimePool(
        profile="cheap-first",
        allow_paid_auto=bool(routing.get("allow_paid_auto", False)),
        allow_frontier_auto=bool(routing.get("allow_frontier_auto", False)),
        tier_call_limits=dict(limits_value),
        candidates=tuple(candidates),
    )


def _candidate_id(binding: RuntimeBinding) -> str:
    if binding.model is None:
        return binding.agent.id
    return f"{binding.agent.id}+{binding.model.provider}/{binding.model.model}"


def _eligible(
    pool: RuntimePool,
    policy: ExecutionPolicy,
    activity: str,
    *,
    purpose: str,
    minimum_tier_exclusive: str | None = None,
    exhausted_tiers: frozenset[str] = frozenset(),
) -> tuple[PoolCandidate, ...]:
    values = []
    for candidate in pool.candidates:
        if not candidate.applies_to(activity, purpose) or not policy.allows(candidate.tier):
            continue
        if candidate.tier in exhausted_tiers:
            continue
        if minimum_tier_exclusive is not None and tier_rank(candidate.tier) <= tier_rank(minimum_tier_exclusive):
            continue
        if tier_rank(candidate.tier) >= tier_rank("paid-efficient") and not pool.allow_paid_auto:
            continue
        if candidate.tier == "frontier" and not pool.allow_frontier_auto:
            continue
        values.append(candidate)
    return tuple(sorted(values, key=lambda item: (tier_rank(item.tier), item.order)))


def select_from_runtime_pool(
    root: Path,
    requirements: ExecutionRequirements,
    *,
    availability: dict[str, RuntimeDiscovery] | None = None,
    budgets: tuple[Budget, ...] = (),
    minimum_tier_exclusive: str | None = None,
    purpose: str = "executor",
    work: str | None = None,
) -> PoolSelection | None:
    """Return the cheapest admissible configured binding, or None when routing is not configured."""

    pool = load_runtime_pool(root)
    if pool is None:
        return None
    policy = execution_policy_for(requirements)
    if purpose not in {"executor", "planner", "reviewer"}:
        raise RuntimePoolError("routing.purpose", f"unknown runtime purpose {purpose!r}")
    exhausted_tiers: frozenset[str] = frozenset()
    if work is not None:
        economics = summarize_economics(root, work)
        counts = economics.get("runtime_selections_by_tier", {})
        exhausted = {
            tier for tier, limit in pool.tier_call_limits.items() if int(counts.get(tier, 0)) >= limit
        }
        if int(economics.get("unaccounted_paid_usage", 0)) > 0:
            exhausted.update({"paid-efficient", "paid-standard", "frontier"})
        exhausted_tiers = frozenset(exhausted)
    candidates = _eligible(
        pool,
        policy,
        requirements.activity_class,
        purpose=purpose,
        minimum_tier_exclusive=minimum_tier_exclusive,
        exhausted_tiers=exhausted_tiers,
    )
    if not candidates:
        raise RuntimePoolError(
            "routing.no_candidate",
            f"no automatic {purpose} candidate is permitted for "
            f"{requirements.activity_class}/{requirements.reasoning_tier}",
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
