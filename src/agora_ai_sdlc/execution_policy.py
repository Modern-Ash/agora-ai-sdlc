"""Deterministic cost policy for generative execution.

Laya classifies the amount of reasoning required; this module translates that
provider-neutral signal into an economic ceiling. It never selects a provider
or grants workflow authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from agora_ai_sdlc.execution_requirements import ExecutionRequirements

EXECUTION_TIERS = ("local", "free", "paid-efficient", "paid-standard", "frontier")
_TIER_INDEX = {name: index for index, name in enumerate(EXECUTION_TIERS)}


class ExecutionPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionPolicy:
    profile: str
    preferred_tier: str
    max_automatic_tier: str
    planner_tier: str | None
    reasoning_tier: str
    paid_execution_allowed: bool
    frontier_allowed: bool
    planner_mode: str = "none"

    def allows(self, tier: str) -> bool:
        if tier not in _TIER_INDEX:
            raise ExecutionPolicyError(f"unknown execution tier {tier!r}")
        return _TIER_INDEX[tier] <= _TIER_INDEX[self.max_automatic_tier]


def tier_rank(tier: str) -> int:
    try:
        return _TIER_INDEX[tier]
    except KeyError as error:
        raise ExecutionPolicyError(f"unknown execution tier {tier!r}") from error


def execution_policy_for(requirements: ExecutionRequirements) -> ExecutionPolicy:
    """Map advisory reasoning demand to a cheapest-capable execution ceiling."""

    if requirements.human_authority_required or requirements.reasoning_tier == "human":
        raise ExecutionPolicyError("human-authority requirements are not executable")

    reasoning = requirements.reasoning_tier
    if reasoning == "local":
        maximum = "paid-efficient"
    elif reasoning == "standard":
        maximum = "paid-standard"
    elif reasoning == "frontier":
        maximum = "frontier"
    else:
        raise ExecutionPolicyError(f"unsupported reasoning tier {reasoning!r}")

    planner_mode = requirements.planner_needed
    planner = None
    if planner_mode == "local":
        planner = "free"
    elif planner_mode == "generative":
        planner = "paid-efficient"
    elif planner_mode == "frontier":
        planner = "frontier"

    return ExecutionPolicy(
        profile="cheap-first",
        preferred_tier="local",
        max_automatic_tier=maximum,
        planner_tier=planner,
        planner_mode=planner_mode,
        reasoning_tier=reasoning,
        paid_execution_allowed=tier_rank(maximum) >= tier_rank("paid-efficient"),
        frontier_allowed=maximum == "frontier",
    )
