import agora.application
import pytest
from agora.application import AgoraReadService

from agora_ai_sdlc import profile_activation
from agora_ai_sdlc.profile_activation import ProfileActivationError, activation_kind, adoption_profiles
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle
from agora_ai_sdlc.studio_projection import PROJECTION_SCHEMA, projector

needs_core_projection = pytest.mark.skipif(
    not hasattr(agora.application, "FlavorProjectionContribution"),
    reason="flavor projection needs Agora Core >=0.9",
)


@pytest.fixture
def life(tmp_path):
    life = Lifecycle(tmp_path / "project", tmp_path / "home")
    life.to_intent()
    return life


def profiles_section(life):
    service = AgoraReadService.from_path(life.root, flavor_projectors=(projector,))
    return service.flavor_projection(PROJECTION_SCHEMA, "selected-profile", SWARM, WORK).to_dict()["profiles"]


def test_packaged_adoption_profiles_and_their_depth_come_from_the_flavor_assets():
    assert adoption_profiles() == {
        "enterprise": "comprehensive",
        "modernization": "comprehensive",
        "regulated": "regulated",
        "starter": "standard",
    }


def test_unknown_profiles_are_rejected_and_kinds_round_trip():
    with pytest.raises(ProfileActivationError, match="profile.unknown"):
        activation_kind("made-up")
    assert activation_kind("starter") == "active-profile-starter"
    assert profile_activation.profile_id_from_kind("active-profile-starter") == "starter"
    assert profile_activation.profile_id_from_kind("intent") is None
    assert profile_activation.profile_id_from_kind("active-profile-") is None


def test_record_states_the_profile_and_disclaims_authority():
    text = profile_activation.render_record("regulated")
    assert "profile: regulated" in text and "depth: regulated" in text
    assert "Authority to change it comes from Agora Core roles" in text


@needs_core_projection
def test_without_a_recorded_activation_profiles_stay_unavailable(life):
    section = profiles_section(life)
    assert section["status"] == "unavailable"
    assert section["reason"]["code"] == "projection.profiles-unavailable"


@needs_core_projection
def test_recorded_activations_project_active_profiles_with_who_and_when(life):
    profile_activation.activate(life.ws, SWARM, WORK, "po", "enterprise")
    profile_activation.activate(life.ws, SWARM, WORK, "po", "regulated")
    section = profiles_section(life)

    assert section["status"] == "available"
    by_id = {item["id"]: item for item in section["value"]}
    assert set(by_id) == {"enterprise", "modernization", "regulated", "starter"}
    assert by_id["regulated"] == {
        **by_id["regulated"],
        "depth": "regulated",
        "active": True,
        "recorded_by": "project:po",
    }
    assert by_id["enterprise"]["active"] is True and by_id["enterprise"]["depth"] == "comprehensive"
    assert by_id["starter"]["active"] is False and "recorded_by" not in by_id["starter"]


@needs_core_projection
def test_unrecognized_activation_kinds_are_shown_with_unknown_depth_not_hidden(life):
    (life.root / "ai-sdlc").mkdir(exist_ok=True)
    (life.root / "ai-sdlc" / "other.md").write_text("# other\n", encoding="utf-8")
    from agora.model import AddArtifactInput

    life.ws.add_artifact(AddArtifactInput(SWARM, WORK, "po", "active-profile-experimental", "repo://ai-sdlc/other.md"))
    by_id = {item["id"]: item for item in profiles_section(life)["value"]}
    assert by_id["experimental"]["depth"] == "unknown" and by_id["experimental"]["active"] is True


@needs_core_projection
def test_other_artifact_kinds_never_count_as_activation(life):
    life.artifact("po", "intent")
    assert profiles_section(life)["status"] == "unavailable"
