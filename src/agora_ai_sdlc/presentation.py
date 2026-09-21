"""Render one canonical lifecycle state through a compatibility profile's presentation stages.

Presentation is a non-authoritative view: Core state and transitions are never changed. The same work item can be
shown as the AWS-original 3 stages or the LG-enterprise 5 stages purely by choosing a profile.
"""

from __future__ import annotations

from agora_ai_sdlc.compatibility_profiles import CompatibilityProfile, load_profile

# Canonical order of Core lifecycle states; `completed` is terminal and follows every presented stage.
CANONICAL_ORDER = ("readiness", "intent", "inception", "construction", "operations", "completed")
DEFAULT_LABELS = {
    "readiness": "Readiness",
    "intent": "Intent",
    "inception": "Inception",
    "construction": "Construction",
    "operations": "Operations",
    "completed": "Completed",
}


def state_labels(profile: CompatibilityProfile) -> dict[str, str]:
    """Canonical state -> presentation label. States a profile does not present keep their canonical label."""

    labels = dict(DEFAULT_LABELS)
    for stage in profile.stages:
        for element in stage.maps_from:
            labels[element] = stage.label
    return labels


def stage_for_state(profile: CompatibilityProfile, state: str) -> str | None:
    """Presentation stage id containing a canonical state, or None when the profile does not present it."""

    for stage in profile.stages:
        if state in stage.maps_from:
            return stage.id
    return None


def stage_view(profile: CompatibilityProfile, state: str) -> dict:
    """Stage list with done/current/upcoming status for a canonical state."""

    if state not in CANONICAL_ORDER:
        raise ValueError(f"unknown canonical state {state!r}")
    position = CANONICAL_ORDER.index(state)
    stages = []
    for stage in profile.stages:
        indexes = [CANONICAL_ORDER.index(element) for element in stage.maps_from]
        if state in stage.maps_from:
            status = "current"
        elif position > max(indexes):
            status = "done"
        else:
            status = "upcoming"
        stages.append({"id": stage.id, "label": stage.label, "maps_from": list(stage.maps_from), "status": status})
    return {
        "profile": {"id": profile.id, "version": profile.version},
        "state": state,
        "current": stage_for_state(profile, state),
        "stages": stages,
    }


def render(profile_id: str, state: str) -> dict:
    return stage_view(load_profile(profile_id), state)
