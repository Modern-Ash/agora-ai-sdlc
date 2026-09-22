"""Deterministic adaptive pathway policy for AI-SDLC plans."""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from agora_ai_sdlc.depth_profiles import ORDER, asset_root
from agora_ai_sdlc.plans import Plan, PlanError, assert_executable
from agora_ai_sdlc.profile_activation import adoption_profiles

POLICY_SET_SCHEMA = "agora-ai-sdlc/pathway-policy-set/v1"
PATHWAY_SCHEMA = "agora-ai-sdlc/pathway/v1"
EXPECTED_LIFECYCLE = ("inception", "construction", "operations")


class AdaptivePlanningError(ValueError):
    """Stable policy-validation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class PathwayPolicy:
    id: str
    minimum_depth: str
    mandatory_steps: tuple[str, ...]
    optional_steps: tuple[str, ...]
    forbidden_skips: tuple[str, ...]
    depth_exemptions: tuple[str, ...] = ()

    @property
    def allowed_steps(self) -> frozenset[str]:
        return frozenset(self.mandatory_steps) | frozenset(self.optional_steps)


@dataclass(frozen=True)
class PolicySet:
    version: str
    method_version: str
    lifecycle: tuple[str, ...]
    depth_order: tuple[str, ...]
    depth_requirements: dict[str, tuple[str, ...]]
    step_vocabulary: tuple[str, ...]


@dataclass(frozen=True)
class AdaptivePlanDecision:
    pathway: str
    effective_depth: str
    mandatory_steps: tuple[str, ...]
    executed_steps: tuple[str, ...]
    skipped_steps: tuple[str, ...]

    def snapshot(self) -> dict:
        return {
            "pathway": self.pathway,
            "effective_depth": self.effective_depth,
            "mandatory_steps": list(self.mandatory_steps),
            "executed_steps": list(self.executed_steps),
            "skipped_steps": list(self.skipped_steps),
            "authorized": True,
            "method_version": "0.2.0",
            "lifecycle": list(EXPECTED_LIFECYCLE),
        }


def _strings(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise AdaptivePlanningError("pathway.type", f"{field!r} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise AdaptivePlanningError("pathway.type", f"{field!r} must not be empty")
    if len(set(value)) != len(value):
        raise AdaptivePlanningError("pathway.duplicate", f"{field!r} contains duplicates")
    return tuple(value)


def load_policy_set() -> PolicySet:
    path = asset_root("profiles") / "pathways" / "policy.yaml"
    if not path.is_file():
        raise AdaptivePlanningError("pathway.policy_missing", f"missing shared pathway policy: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != POLICY_SET_SCHEMA:
        raise AdaptivePlanningError("pathway.policy_schema", "invalid pathway policy-set schema")
    lifecycle = _strings(data.get("lifecycle"), "lifecycle")
    if lifecycle != EXPECTED_LIFECYCLE:
        raise AdaptivePlanningError(
            "pathway.lifecycle",
            f"all pathways must use the shared lifecycle {EXPECTED_LIFECYCLE!r}",
        )
    method = data.get("method")
    if not isinstance(method, dict) or method.get("id") != "ai-sdlc" or method.get("version") != "0.2.0":
        raise AdaptivePlanningError("pathway.method", "adaptive pathways require AI-SDLC Method Pack 0.2.0")
    depth_order = _strings(data.get("depth_order"), "depth_order")
    if tuple(depth_order) != ORDER:
        raise AdaptivePlanningError("pathway.depth_order", f"depth order must match {ORDER!r}")
    vocabulary = _strings(data.get("step_vocabulary"), "step_vocabulary")
    depth_raw = data.get("depth_requirements")
    if not isinstance(depth_raw, dict) or set(depth_raw) != set(depth_order):
        raise AdaptivePlanningError("pathway.depth_requirements", "depth requirements must cover every depth")
    depth_requirements = {
        depth: _strings(depth_raw[depth], f"depth_requirements.{depth}", allow_empty=True) for depth in depth_order
    }
    known = set(vocabulary)
    for depth, items in depth_requirements.items():
        unknown = sorted(set(items) - known)
        if unknown:
            raise AdaptivePlanningError(
                "pathway.step_unknown",
                f"depth {depth!r} references unknown steps: {', '.join(unknown)}",
            )
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise AdaptivePlanningError("pathway.version", "policy version must be a non-empty string")
    return PolicySet(version, "0.2.0", lifecycle, depth_order, depth_requirements, vocabulary)


def load_pathway(pathway_id: str) -> PathwayPolicy:
    policy_set = load_policy_set()
    path = asset_root("profiles") / "pathways" / f"{pathway_id}.yaml"
    if not path.is_file():
        raise AdaptivePlanningError("pathway.unknown", f"unknown pathway {pathway_id!r}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != PATHWAY_SCHEMA or data.get("id") != pathway_id:
        raise AdaptivePlanningError("pathway.schema", f"invalid pathway profile {pathway_id!r}")
    expected = {"schema", "id", "minimum_depth", "mandatory_steps", "optional_steps", "forbidden_skips"}
    allowed = expected | {"depth_exemptions"}
    if not expected <= set(data) or not set(data) <= allowed:
        raise AdaptivePlanningError("pathway.fields", f"{pathway_id!r} has invalid fields")
    minimum_depth = data["minimum_depth"]
    if minimum_depth not in policy_set.depth_order:
        raise AdaptivePlanningError("pathway.depth", f"invalid minimum depth {minimum_depth!r}")
    mandatory = _strings(data["mandatory_steps"], "mandatory_steps")
    optional = _strings(data["optional_steps"], "optional_steps", allow_empty=True)
    forbidden = _strings(data["forbidden_skips"], "forbidden_skips", allow_empty=True)
    exemptions = _strings(data.get("depth_exemptions", []), "depth_exemptions", allow_empty=True)

    known = set(policy_set.step_vocabulary)
    all_steps = set(mandatory) | set(optional)
    unknown = sorted((all_steps | set(exemptions)) - known)
    if unknown:
        raise AdaptivePlanningError("pathway.step_unknown", f"unknown pathway steps: {', '.join(unknown)}")
    if set(mandatory) & set(optional):
        raise AdaptivePlanningError("pathway.step_overlap", "mandatory and optional steps must be disjoint")
    if not set(forbidden) <= all_steps:
        raise AdaptivePlanningError("pathway.forbidden_unknown", "forbidden-skips must be declared by the pathway")

    min_index = policy_set.depth_order.index(minimum_depth)
    required_at_or_above = set()
    for depth in policy_set.depth_order[min_index:]:
        required_at_or_above.update(policy_set.depth_requirements[depth])
    missing_depth_steps = sorted(required_at_or_above - set(exemptions) - all_steps)
    if missing_depth_steps:
        raise AdaptivePlanningError(
            "pathway.depth_coverage",
            f"pathway cannot support stricter depth obligations: {', '.join(missing_depth_steps)}",
        )

    return PathwayPolicy(pathway_id, minimum_depth, mandatory, optional, forbidden, exemptions)


def available_pathways() -> tuple[str, ...]:
    root = asset_root("profiles") / "pathways"
    if not root.is_dir():
        return ()
    return tuple(path.stem for path in sorted(root.glob("*.yaml")) if path.name != "policy.yaml")


def effective_depth(
    pathway: PathwayPolicy,
    *,
    depth: str | None = None,
    adoption_profile: str | None = None,
) -> str:
    """Return the strictest of pathway minimum, explicit depth and adoption profile depth."""

    policy_set = load_policy_set()
    candidates = [pathway.minimum_depth]
    if depth is not None:
        if depth not in policy_set.depth_order:
            raise AdaptivePlanningError("pathway.depth", f"unknown depth {depth!r}")
        candidates.append(depth)
    if adoption_profile is not None:
        profiles = adoption_profiles()
        if adoption_profile not in profiles:
            raise AdaptivePlanningError("pathway.profile", f"unknown adoption profile {adoption_profile!r}")
        candidates.append(profiles[adoption_profile])
    return max(candidates, key=policy_set.depth_order.index)


def _mandatory_for(pathway: PathwayPolicy, depth: str) -> tuple[str, ...]:
    policy_set = load_policy_set()
    depth_index = policy_set.depth_order.index(depth)
    promoted = set(pathway.mandatory_steps)
    for current in policy_set.depth_order[: depth_index + 1]:
        promoted.update(policy_set.depth_requirements[current])
    promoted.difference_update(pathway.depth_exemptions)
    return tuple(step for step in policy_set.step_vocabulary if step in promoted)


def validate_adaptive_plan(
    plan: Plan,
    pathway_id: str,
    *,
    depth: str | None = None,
    adoption_profile: str | None = None,
) -> AdaptivePlanDecision:
    """Validate an approved plan against one adaptive pathway policy."""

    pathway = load_pathway(pathway_id)
    chosen_depth = effective_depth(pathway, depth=depth, adoption_profile=adoption_profile)

    try:
        assert_executable(plan)
    except PlanError as error:
        raise AdaptivePlanningError("pathway.plan_not_approved", str(error)) from error

    by_id = {step.id: step for step in plan.steps}
    unknown = sorted(set(by_id) - pathway.allowed_steps)
    if unknown:
        raise AdaptivePlanningError(
            "pathway.step_not_allowed",
            f"pathway {pathway_id!r} does not allow steps: {', '.join(unknown)}",
        )

    mandatory = _mandatory_for(pathway, chosen_depth)
    missing = [step for step in mandatory if step not in by_id]
    if missing:
        raise AdaptivePlanningError(
            "pathway.mandatory_missing",
            f"required steps are missing at depth {chosen_depth!r}: {', '.join(missing)}",
        )

    forbidden_skip = set(pathway.forbidden_skips) | set(mandatory)
    skipped_forbidden = sorted(step.id for step in plan.steps if step.decision == "skip" and step.id in forbidden_skip)
    if skipped_forbidden:
        raise AdaptivePlanningError(
            "pathway.mandatory_skip",
            f"mandatory/protected steps cannot be skipped: {', '.join(skipped_forbidden)}",
        )

    executed = tuple(step.id for step in plan.steps if step.decision == "execute")
    skipped = tuple(step.id for step in plan.steps if step.decision == "skip")
    return AdaptivePlanDecision(pathway_id, chosen_depth, mandatory, executed, skipped)
