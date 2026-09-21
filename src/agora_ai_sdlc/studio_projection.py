"""AI-SDLC provider for Agora Core's flavor projection boundary (`agora-ai-sdlc/studio-projection/v1`).

The provider is a pure adapter over the immutable Core context it receives: no filesystem, network or
`.agora/` reads except the flavor's own packaged manifest and contract schema. Core owns project identity,
lifecycle, clarifications and the snapshot; this module supplies only the flavor-owned sections. Anything Core
does not yet expose is an explicit `unavailable` section with a stable reason, never a guess.

Requires Agora Core >=0.9 at projection time; the module itself imports on any supported Core.

Wire it into Agora Studio at startup: `agora-studio --flavor-projector agora_ai_sdlc.studio_projection:projector`.
Use `:aws_original_projector` or `:lg_enterprise_projector` to present the same work through a compatibility profile's stages.
"""

import json
from typing import TYPE_CHECKING

from agora_ai_sdlc.compatibility_profiles import load_profile
from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.flavor_manifest import SCHEMA as MANIFEST_SCHEMA
from agora_ai_sdlc.flavor_manifest import load_packaged_manifest
from agora_ai_sdlc.presentation import stage_view, state_labels
from agora_ai_sdlc.profile_activation import adoption_profiles, profile_id_from_kind

if TYPE_CHECKING:
    from agora.application import FlavorProjectionContext, FlavorProjectionContribution

PROJECTION_SCHEMA = "agora-ai-sdlc/studio-projection/v1"
SECTIONS = ("flavor", "profiles", "provenance", "separation", "metrics")
SECTION_ORDER = ["lifecycle", "clarifications", "separation", "provenance", "metrics"]
STATE_LABELS = {
    "readiness": "Readiness",
    "intent": "Intent",
    "inception": "Inception",
    "construction": "Construction",
    "operations": "Operations",
    "completed": "Completed",
}


def _unavailable(code: str, message: str) -> dict[str, object]:
    return {"status": "unavailable", "reason": {"code": code, "message": message}}


def _field(source: str, value: str | None) -> dict[str, object]:
    if source == "unavailable" or not value:
        return {"source": "unavailable", "value": None}
    return {"source": source, "value": value}


def _execution(session: object) -> dict[str, object]:
    """Map one Core session (0.9+ provenance, or the 0.8 fields) without upgrading trust."""
    provenance = getattr(session, "provenance", None)
    integration, provider, model = session.integration, session.provider, session.model  # type: ignore[attr-defined]
    if provenance is None or provenance.selection_reason is None:
        basis = dict.fromkeys(("runtime", "provider", "model"), "declared")
        if provenance is not None:
            basis = {
                "runtime": provenance.runtime_basis,
                "provider": provenance.provider_basis,
                "model": provenance.model_basis,
            }
        fallback: dict[str, object] = {"source": "unavailable", "used": None, "from": None, "reason": None}
        version = _field("unavailable", None)
        reason = _field("unavailable", None)
    else:
        basis = {
            "runtime": provenance.runtime_basis,
            "provider": provenance.provider_basis,
            "model": provenance.model_basis,
        }
        version = _field("declared", provenance.runtime_version)
        reason = _field("declared", provenance.selection_reason)
        if provenance.fallback_used:
            origin = {
                "runtime": provenance.fallback_from_integration,
                "provider": provenance.fallback_from_provider,
                "model": provenance.fallback_from_model,
            }
            complete = all(origin.values()) and provenance.fallback_reason
            fallback = (
                {"source": "declared", "used": True, "from": origin, "reason": provenance.fallback_reason}
                if complete
                else {"source": "unavailable", "used": None, "from": None, "reason": None}
            )
        else:
            fallback = {"source": "declared", "used": False, "from": None, "reason": None}
    return {
        "session_id": session.id,  # type: ignore[attr-defined]
        "actor": session.executor or session.actor,  # type: ignore[attr-defined]
        "runtime": _field(basis["runtime"], integration),
        "runtime_version": version,
        "provider": _field(basis["provider"], provider),
        "model": _field(basis["model"], model),
        "selection_reason": reason,
        "fallback": fallback,
    }


def _profiles(artifacts: object) -> dict[str, object]:
    """Active profiles recorded as Core artifacts (see profile_activation); latest record per profile wins."""
    latest: dict[str, object] = {}
    for artifact in artifacts:  # type: ignore[attr-defined]
        profile = profile_id_from_kind(artifact.kind)
        if profile is not None and (profile not in latest or artifact.timestamp >= latest[profile].timestamp):
            latest[profile] = artifact
    if not latest:
        return _unavailable(
            "projection.profiles-unavailable",
            "No adoption profile activation is recorded for this work",
        )
    known = adoption_profiles()
    items = []
    for profile in sorted({*known, *latest}):
        item: dict[str, object] = {"id": profile, "depth": known.get(profile, "unknown"), "active": profile in latest}
        if profile in latest:
            item["recorded_by"] = latest[profile].produced_by  # type: ignore[attr-defined]
            item["recorded_at"] = latest[profile].timestamp  # type: ignore[attr-defined]
        items.append(item)
    return {"status": "available", "value": items}


class AiSdlcProjectionProvider:
    """Core `FlavorProjectionProvider` for the AI-SDLC flavor."""

    projection_schema = PROJECTION_SCHEMA
    required_sections = SECTIONS

    def __init__(self, presentation_profile: str | None = None) -> None:
        """`presentation_profile` (a compatibility profile id) only relabels and groups Core states."""
        self.presentation_profile = presentation_profile

    @property
    def projection_schema_document(self) -> dict[str, object]:
        path = asset_root("contracts") / "studio" / "ai-sdlc-projection-v1.schema.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def project(self, context: "FlavorProjectionContext") -> "FlavorProjectionContribution":
        try:
            from agora.application import FlavorProjectionContribution
        except ImportError as error:
            raise RuntimeError(
                "the AI-SDLC Studio projection requires Agora Core >=0.9 (flavor projection boundary)"
            ) from error
        manifest = load_packaged_manifest()
        executions = [_execution(session) for session in context.sessions]
        sections: dict[str, object] = {
            "flavor": {
                "status": "available",
                "value": {
                    "id": manifest.id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "manifest_schema": MANIFEST_SCHEMA,
                    "supported_core": manifest.supported_core,
                },
            },
            "profiles": _profiles(context.work.artifacts),
            "provenance": (
                {
                    "status": "available",
                    "value": {"source_schema": "agora/application/session-summary/v1", "executions": executions},
                }
                if executions
                else _unavailable(
                    "projection.provenance-unavailable", "No execution session is associated with this work"
                )
            ),
            "separation": _unavailable(
                "projection.separation-unavailable",
                "No Core extension projection transports the reviewed-artifact facts needed to evaluate separation",
            ),
            "metrics": _unavailable(
                "projection.metrics-unavailable", "No Core-backed AI-SDLC metric window is available"
            ),
        }
        presentation: dict[str, object] = {
            "authoritative": False,
            "labels": dict(STATE_LABELS),
            "section_order": SECTION_ORDER,
        }
        if self.presentation_profile is not None:
            profile = load_profile(self.presentation_profile)
            presentation["labels"] = state_labels(profile)
            presentation["stages"] = stage_view(profile, context.lifecycle.current_state)
        return FlavorProjectionContribution(sections=sections, presentation=presentation)


projector = AiSdlcProjectionProvider()
aws_original_projector = AiSdlcProjectionProvider("aws-original")
lg_enterprise_projector = AiSdlcProjectionProvider("lg-enterprise")
