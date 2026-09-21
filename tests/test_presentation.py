import agora.application
import pytest

from agora_ai_sdlc.compatibility_profiles import load_profile
from agora_ai_sdlc.presentation import CANONICAL_ORDER, render, stage_for_state, stage_view, state_labels
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle
from agora_ai_sdlc.studio_projection import (
    PROJECTION_SCHEMA,
    AiSdlcProjectionProvider,
    aws_original_projector,
    lg_enterprise_projector,
)

LG = ["initialization", "ideation", "inception", "construction", "operation"]
AWS = ["inception", "construction", "operations"]


def statuses(view):
    return {stage["id"]: stage["status"] for stage in view["stages"]}


def test_lg_enterprise_presents_five_stages_over_canonical_states():
    profile = load_profile("lg-enterprise")
    assert profile.version == "1.0.0"
    assert [s.id for s in profile.stages] == LG
    assert [stage_for_state(profile, state) for state in CANONICAL_ORDER] == [
        "initialization",
        "ideation",
        "inception",
        "construction",
        "operation",
        None,
    ]
    assert state_labels(profile)["operations"] == "Operation"
    assert state_labels(profile)["readiness"] == "Initialization"


def test_same_state_renders_as_aws_original_or_lg_enterprise():
    aws = render("aws-original", "intent")
    lg = render("lg-enterprise", "intent")
    assert [s["id"] for s in aws["stages"]] == AWS and aws["current"] == "inception"
    assert [s["id"] for s in lg["stages"]] == LG and lg["current"] == "ideation"
    assert statuses(lg) == {
        "initialization": "done",
        "ideation": "current",
        "inception": "upcoming",
        "construction": "upcoming",
        "operation": "upcoming",
    }
    assert statuses(aws)["inception"] == "current"


@pytest.mark.parametrize("profile_id", ["aws-original", "lg-enterprise"])
def test_progress_is_monotonic_and_completed_finishes_every_stage(profile_id):
    profile = load_profile(profile_id)
    done_counts = [
        sum(stage["status"] == "done" for stage in stage_view(profile, state)["stages"]) for state in CANONICAL_ORDER
    ]
    assert done_counts == sorted(done_counts)
    assert set(statuses(stage_view(profile, "completed")).values()) == {"done"}


def test_unpresented_state_has_no_current_stage_and_unknown_state_fails():
    aws = render("aws-original", "readiness")
    assert aws["current"] is None and set(statuses(aws).values()) == {"upcoming"}
    with pytest.raises(ValueError):
        render("lg-enterprise", "nonsense")


pytestmark_core = pytest.mark.skipif(
    not hasattr(agora.application, "FlavorProjectionContribution"), reason="flavor projection needs Agora Core >=0.9"
)


def project(tmp_path, provider, advance=None):
    life = Lifecycle(tmp_path / "project", tmp_path / "home")
    life.to_intent()
    if advance:
        advance(life)
    service = agora.application.AgoraReadService.from_path(life.root, flavor_projectors=(provider,))
    return service.flavor_projection(PROJECTION_SCHEMA, "selected-test0001", SWARM, WORK).to_dict()


@pytestmark_core
def test_studio_projection_renders_both_views_without_changing_core_state(tmp_path):
    aws = project(tmp_path / "a", aws_original_projector, lambda life: life.to_inception())
    lg = project(tmp_path / "b", lg_enterprise_projector, lambda life: life.to_inception())

    assert aws["lifecycle"]["value"]["current_state"] == lg["lifecycle"]["value"]["current_state"] == "inception"
    assert aws["presentation"]["authoritative"] is False and lg["presentation"]["authoritative"] is False
    assert [s["id"] for s in aws["presentation"]["stages"]["stages"]] == AWS
    assert [s["id"] for s in lg["presentation"]["stages"]["stages"]] == LG
    assert lg["presentation"]["stages"]["current"] == "inception"
    assert lg["presentation"]["labels"]["operations"] == "Operation"
    assert lg["presentation"]["stages"]["profile"] == {"id": "lg-enterprise", "version": "1.0.0"}


@pytestmark_core
def test_default_projector_is_unchanged(tmp_path):
    from agora_ai_sdlc.studio_projection import projector

    result = project(tmp_path, projector)
    assert "stages" not in result["presentation"]
    assert result["presentation"]["labels"]["intent"] == "Intent"
    assert AiSdlcProjectionProvider().presentation_profile is None
