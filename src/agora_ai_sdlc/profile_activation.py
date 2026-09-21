"""Record which AI-SDLC adoption profile is active for a Unit of Work, using ordinary Core artifacts.

Agora Core has no notion of a flavor profile, and the flavor projection provider is a pure adapter over the
Core context, so the fact "profile X is active" is recorded as a Core artifact whose kind is
`active-profile-<id>` and whose repository file carries the profile id and depth. Recording is attributable
(`produced_by`, timestamp) and append-only; the latest record per profile wins. It is a recorded fact, not an
authorization: role authority still comes from Core, and the projection reports who recorded it.
"""

from pathlib import Path

import yaml

from agora_ai_sdlc.depth_profiles import asset_root

KIND_PREFIX = "active-profile-"
SCHEMA = "agora-ai-sdlc/profile-activation/v1"
ADOPTION_SCHEMA = "agora-ai-sdlc/adoption-profile/v1"


class ProfileActivationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def adoption_profiles() -> dict[str, str]:
    """Packaged adoption profiles and their depth, read from the flavor's own assets."""
    found: dict[str, str] = {}
    for path in sorted(asset_root("profiles").glob("*/profile.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("schema") == ADOPTION_SCHEMA:
            found[str(data["id"])] = str(data["depth"])
    return found


def activation_kind(profile_id: str) -> str:
    if profile_id not in adoption_profiles():
        raise ProfileActivationError("profile.unknown", f"unknown adoption profile {profile_id!r}")
    return f"{KIND_PREFIX}{profile_id}"


def profile_id_from_kind(kind: str) -> str | None:
    return kind[len(KIND_PREFIX) :] if kind.startswith(KIND_PREFIX) and len(kind) > len(KIND_PREFIX) else None


def relative_path(profile_id: str) -> str:
    return f"ai-sdlc/profiles/{activation_kind(profile_id)}.md"


def render_record(profile_id: str) -> str:
    activation_kind(profile_id)
    depth = adoption_profiles()[profile_id]
    return (
        f"---\nschema: {SCHEMA}\nprofile: {profile_id}\ndepth: {depth}\n---\n"
        f"# Active profile: {profile_id}\n\n"
        "Records that this adoption profile governs the work it is attached to. Authority to change "
        "it comes from Agora Core roles, not from this file.\n"
    )


def write_record(project_root: Path, profile_id: str) -> str:
    """Write the activation file inside the project and return its `repo://` URI."""
    relative = relative_path(profile_id)
    target = project_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_record(profile_id), encoding="utf-8")
    return f"repo://{relative}"


def activate(workspace, swarm_id: str, work_id: str, actor_id: str, profile_id: str):
    """Register the activation with Core (unsigned actors); signed actors use `prepare`."""
    from agora.model import AddArtifactInput

    uri = write_record(workspace.project_root(), profile_id)
    return workspace.add_artifact(
        AddArtifactInput(
            swarm_id=swarm_id, work_id=work_id, actor_id=actor_id, kind=activation_kind(profile_id), uri=uri
        )
    )


def prepare(workspace, swarm_id: str, work_id: str, actor_id: str, profile_id: str, action_id: str):
    """Prepare the activation as a Core lifecycle action so an authenticated actor can sign it."""
    from agora.model import PrepareArtifactInput

    uri = write_record(workspace.project_root(), profile_id)
    return workspace.prepare_add_artifact(
        PrepareArtifactInput(swarm_id, work_id, actor_id, activation_kind(profile_id), uri, id=action_id)
    )
