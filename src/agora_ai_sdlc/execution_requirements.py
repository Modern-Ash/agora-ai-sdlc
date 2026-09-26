"""Provider-neutral ExecutionRequirements: deterministic facts plus accepted advisory signals.

Advisory signals (Laya) can only tighten requirements. They never name a runtime, select a
model, remove a deterministic capability, or approve anything.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agora_ai_sdlc.agent_capabilities import CAPABILITY_IDS
from agora_ai_sdlc.decision_plane import (
    DecisionEvaluation,
    DecisionPlaneError,
    DecisionProvider,
)
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_decisions import advise_execution

REQUIREMENTS_SCHEMA = "agora-ai-sdlc/execution-requirements/v1"
TIERS = ("local", "standard", "frontier", "human")
RISKS = ("low", "moderate", "high")
FOCI = ("functional", "security", "performance", "architecture", "operations")
SECURITY = ("normal", "required")

_READ = ("workspace.read",)
_ACTIVITY_CAPABILITIES: Mapping[str, tuple[str, ...]] = {
    "exploration.read_only": (*_READ, "git.read"),
    "inception.elaboration": (*_READ, "workspace.write"),
    "construction.implementation": (*_READ, "workspace.write", "shell.execute"),
    "operations.verification": (*_READ, "shell.execute"),
    "governance.transition": _READ,
    "human.authority": (),
}
_TIER_FLOOR = {
    "exploration.read_only": "local",
    "inception.elaboration": "standard",
    "construction.implementation": "local",
    "operations.verification": "local",
    "governance.transition": "local",
    "human.authority": "human",
}
_STAGE_ACTIVITY = {
    "inception": "inception.elaboration",
    "construction": "construction.implementation",
    "operations": "operations.verification",
}


@dataclass(frozen=True)
class ExecutionRequirements:
    activity_class: str
    reasoning_tier: str
    risk: str
    security_review: str
    validation_focus: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    human_authority_required: bool
    advisory: Mapping[str, Any]

    @property
    def executable_by_agent(self) -> bool:
        return not self.human_authority_required

    def to_dict(self) -> dict:
        return {
            "schema": REQUIREMENTS_SCHEMA,
            "activity_class": self.activity_class,
            "reasoning_tier": self.reasoning_tier,
            "risk": self.risk,
            "security_review": self.security_review,
            "validation_focus": list(self.validation_focus),
            "required_capabilities": list(self.required_capabilities),
            "human_authority_required": self.human_authority_required,
            "executable_by_agent": self.executable_by_agent,
            "advisory": dict(self.advisory),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def activity_class(bundle: ExecutionBundle) -> str:
    """Deterministic action -> activity class, owned by AI-SDLC."""
    if bundle.next_action == "human-approval" or bundle.governance.get("human_approval_required"):
        return "human.authority"
    if bundle.next_action == "governed-transition":
        return "governance.transition"
    return _STAGE_ACTIVITY.get(bundle.stage or "", "exploration.read_only")


def _accepted_value(evaluation: DecisionEvaluation | None, question: str, allowed: tuple[str, ...]) -> str | None:
    """An accepted answer with an unexpected value is ignored, never trusted."""
    if evaluation is None or question not in evaluation.accepted:
        return None
    answer = evaluation.result.answers.get(question)
    value = getattr(answer, "value", None)
    return value if isinstance(value, str) and value in allowed else None


def _max(order: tuple[str, ...], *values: str | None) -> str:
    return max((value for value in values if value in order), key=order.index)


def project_requirements(
    bundle: ExecutionBundle,
    evaluation: DecisionEvaluation | None = None,
    *,
    independent_review_required: bool = False,
    advisory_error: str | None = None,
) -> ExecutionRequirements:
    activity = activity_class(bundle)
    tier = _max(TIERS, _TIER_FLOOR[activity], _accepted_value(evaluation, "reasoning_tier", TIERS))
    deterministic_risk = "moderate" if bundle.risks else "low"
    risk = _max(RISKS, deterministic_risk, _accepted_value(evaluation, "change_risk", RISKS))
    security = _max(SECURITY, "normal", _accepted_value(evaluation, "security_review", SECURITY))
    focus = {"functional"}
    laya_focus = _accepted_value(evaluation, "validation_focus", FOCI)
    if laya_focus:
        focus.add(laya_focus)
    if security == "required":
        focus.add("security")

    human = activity == "human.authority" or tier == "human"
    capabilities = set() if human else set(_ACTIVITY_CAPABILITIES[activity])
    if not human and security == "required":
        capabilities.update(("workspace.read", "git.read"))
    if not human and independent_review_required:
        capabilities.add("isolated_reviewer")
    unknown = capabilities - set(CAPABILITY_IDS)
    if unknown:
        raise DecisionPlaneError("requirements.capability", f"unknown capability ids: {sorted(unknown)}")

    advisory: dict[str, Any] = {"provider": None, "model": None, "accepted": [], "escalated": [], "confidence": {}}
    if evaluation is not None:
        result = evaluation.result
        advisory = {
            "provider": result.provider,
            "model": result.model,
            "accepted": sorted(evaluation.accepted),
            "escalated": sorted(evaluation.escalated),
            "confidence": {name: round(float(answer.confidence), 4) for name, answer in sorted(result.answers.items())},
        }
    if advisory_error:
        advisory["error"] = advisory_error
    return ExecutionRequirements(
        activity_class=activity,
        reasoning_tier=tier,
        risk=risk,
        security_review=security,
        validation_focus=tuple(sorted(focus)),
        required_capabilities=tuple(name for name in CAPABILITY_IDS if name in capabilities),
        human_authority_required=human,
        advisory=advisory,
    )


def requirements_from_dict(payload: Mapping[str, Any]) -> ExecutionRequirements:
    """Parse and validate a persisted ExecutionRequirements/v1 payload."""

    if not isinstance(payload, Mapping) or payload.get("schema") != REQUIREMENTS_SCHEMA:
        raise DecisionPlaneError("requirements.schema", f"expected schema {REQUIREMENTS_SCHEMA}")
    activity = str(payload.get("activity_class") or "")
    tier = str(payload.get("reasoning_tier") or "")
    risk = str(payload.get("risk") or "")
    security = str(payload.get("security_review") or "")
    focus_raw = payload.get("validation_focus")
    capabilities_raw = payload.get("required_capabilities")
    advisory = payload.get("advisory")
    human = payload.get("human_authority_required")

    if activity not in _ACTIVITY_CAPABILITIES:
        raise DecisionPlaneError("requirements.activity", f"unsupported activity class {activity!r}")
    if tier not in TIERS:
        raise DecisionPlaneError("requirements.tier", f"unsupported reasoning tier {tier!r}")
    if risk not in RISKS:
        raise DecisionPlaneError("requirements.risk", f"unsupported risk {risk!r}")
    if security not in SECURITY:
        raise DecisionPlaneError("requirements.security", f"unsupported security review {security!r}")
    if not isinstance(focus_raw, list) or any(item not in FOCI for item in focus_raw):
        raise DecisionPlaneError("requirements.focus", "validation_focus contains unsupported values")
    if not isinstance(capabilities_raw, list) or any(item not in CAPABILITY_IDS for item in capabilities_raw):
        raise DecisionPlaneError("requirements.capability", "required_capabilities contains unsupported values")
    if not isinstance(advisory, Mapping):
        raise DecisionPlaneError("requirements.advisory", "advisory must be a mapping")
    if not isinstance(human, bool):
        raise DecisionPlaneError("requirements.human_authority", "human_authority_required must be boolean")
    if human != (tier == "human" or activity == "human.authority"):
        raise DecisionPlaneError(
            "requirements.human_authority",
            "human_authority_required is inconsistent with the activity/reasoning tier",
        )

    result = ExecutionRequirements(
        activity_class=activity,
        reasoning_tier=tier,
        risk=risk,
        security_review=security,
        validation_focus=tuple(sorted(dict.fromkeys(str(item) for item in focus_raw))),
        required_capabilities=tuple(name for name in CAPABILITY_IDS if name in set(capabilities_raw)),
        human_authority_required=human,
        advisory=dict(advisory),
    )
    expected = {key: value for key, value in payload.items() if key != "executable_by_agent"}
    actual = {key: value for key, value in result.to_dict().items() if key != "executable_by_agent"}
    if actual != expected:
        raise DecisionPlaneError("requirements.noncanonical", "requirements payload is not canonical")
    return result


def requirements_for(
    bundle: ExecutionBundle,
    provider: DecisionProvider | None = None,
    *,
    confidence_threshold: float = 0.90,
    independent_review_required: bool = False,
) -> ExecutionRequirements:
    """Evaluate the optional advisor; any advisory failure falls back to deterministic requirements."""
    evaluation = None
    error = None
    if provider is not None:
        try:
            evaluation = advise_execution(bundle, provider=provider, confidence_threshold=confidence_threshold)
        except DecisionPlaneError as failure:
            error = failure.code
        except Exception:  # noqa: BLE001 - untrusted provider; never let it break safe defaults
            error = "advisory.unavailable"
    return project_requirements(
        bundle,
        evaluation,
        independent_review_required=independent_review_required,
        advisory_error=error,
    )


def requirements_for_activity(activity: str, *, tier: str = "local") -> ExecutionRequirements:
    """Deterministic requirements for an activity class without a bundle (diagnostics, migration previews)."""
    if activity not in _ACTIVITY_CAPABILITIES:
        raise DecisionPlaneError("requirements.activity", f"unknown activity class {activity!r}")
    human = activity == "human.authority" or tier == "human"
    capabilities = () if human else _ACTIVITY_CAPABILITIES[activity]
    return ExecutionRequirements(
        activity_class=activity,
        reasoning_tier=_max(TIERS, _TIER_FLOOR[activity], tier),
        risk="low",
        security_review="normal",
        validation_focus=("functional",),
        required_capabilities=tuple(name for name in CAPABILITY_IDS if name in capabilities),
        human_authority_required=human,
        advisory={"provider": None, "model": None, "accepted": [], "escalated": [], "confidence": {}},
    )
