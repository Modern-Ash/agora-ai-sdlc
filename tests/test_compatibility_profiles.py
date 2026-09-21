import json
from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.compatibility_profiles import (
    CANONICAL_MODEL,
    SCHEMA,
    CompatibilityProfileError,
    available_profiles,
    load_profile,
    parse_profile,
)

ROOT = Path(__file__).parent.parent


def as_text(data):
    return yaml.safe_dump(data, sort_keys=False)


def packaged(profile_id):
    return yaml.safe_load(
        (ROOT / "profiles" / "compatibility" / profile_id / "profile.yaml").read_text(encoding="utf-8")
    )


def code(data):
    with pytest.raises(CompatibilityProfileError) as exc:
        parse_profile(as_text(data))
    return exc.value.code


def test_packaged_compatibility_profiles_validate_and_are_discoverable():
    assert available_profiles() == ("aws-original", "lg-enterprise")
    aws = load_profile("aws-original")
    lg = load_profile("lg-enterprise")

    assert aws.canonical_model == lg.canonical_model == CANONICAL_MODEL
    assert [stage.id for stage in aws.stages] == ["inception", "construction", "operations"]
    assert aws.stage("inception").maps_from == ("intent", "inception")
    assert [stage.id for stage in lg.stages] == [
        "initialization",
        "ideation",
        "inception",
        "construction",
        "operation",
    ]
    assert lg.stage("initialization").maps_from == ("readiness",)
    assert lg.stage("ideation").maps_from == ("intent",)


@pytest.mark.parametrize("profile_id", ["aws-original", "lg-enterprise"])
def test_capability_sets_are_declared_disjoint_and_neutral(profile_id):
    profile = load_profile(profile_id)
    groups = [
        set(profile.required_capabilities),
        set(profile.optional_capabilities),
        set(profile.unsupported_capabilities),
    ]
    assert all(groups[i].isdisjoint(groups[j]) for i in range(len(groups)) for j in range(i + 1, len(groups)))
    assert profile.neutrality == ("provider", "model", "cloud", "scm", "agent-runtime")
    raw = packaged(profile_id)
    assert raw["source"]["basis"] == "public"
    assert raw["source"]["affiliation"] is False
    assert raw["source"]["runtime_dependency"] is False
    assert all(raw["neutrality"].values())


def test_unknown_canonical_mapping_fails_deterministically():
    data = packaged("lg-enterprise")
    data["stages"][0]["maps_from"] = ["unknown"]
    assert code(data) == "compatibility.mapping_unknown"


def test_duplicate_canonical_mapping_across_stages_fails_deterministically():
    data = packaged("lg-enterprise")
    data["stages"][1]["maps_from"] = ["readiness"]
    assert code(data) == "compatibility.mapping_duplicate"


def test_duplicate_stage_id_fails_deterministically():
    data = packaged("lg-enterprise")
    data["stages"][1]["id"] = "initialization"
    assert code(data) == "compatibility.stage_duplicate"


def test_capability_overlap_fails_deterministically():
    data = packaged("aws-original")
    data["capabilities"]["optional"].append(data["capabilities"]["required"][0])
    assert code(data) == "compatibility.capability_overlap"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda data: data.update({"schema": "agora-ai-sdlc/compatibility-profile/v2"}), "compatibility.schema"),
        (lambda data: data.update({"version": "1.0"}), "compatibility.version"),
        (lambda data: data["source"].update({"basis": "private"}), "compatibility.source_scope"),
        (lambda data: data["source"].update({"affiliation": True}), "compatibility.affiliation"),
        (lambda data: data["neutrality"].update({"cloud": False}), "compatibility.neutrality"),
    ],
)
def test_invalid_contracts_fail_closed(mutation, expected):
    data = packaged("aws-original")
    mutation(data)
    assert code(data) == expected


def test_checked_in_json_schema_matches_runtime_contract():
    schema = json.loads(
        (ROOT / "contracts" / "conformance" / "compatibility-profile-v1.schema.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema"]["const"] == SCHEMA
    assert schema["properties"]["canonical_model"]["const"] == CANONICAL_MODEL
    assert set(schema["required"]) == {
        "schema",
        "id",
        "name",
        "version",
        "canonical_model",
        "source",
        "stages",
        "capabilities",
        "neutrality",
    }


def test_unknown_profile_and_stage_have_stable_codes():
    with pytest.raises(CompatibilityProfileError) as exc:
        load_profile("missing")
    assert exc.value.code == "compatibility.profile_unknown"
    with pytest.raises(CompatibilityProfileError) as exc:
        load_profile("aws-original").stage("missing")
    assert exc.value.code == "compatibility.stage_unknown"
