import copy
import json
import re

import pytest

from agora_ai_sdlc.depth_profiles import asset_root

ROOT = asset_root("contracts") / "studio"
SCHEMA_ID = "agora-ai-sdlc/studio-projection/v1"
SECTIONS = ("flavor", "profiles", "lifecycle", "clarifications", "provenance", "separation", "metrics")
FORBIDDEN_KEYS = {
    "path",
    "filesystem_path",
    "project_path",
    "root",
    "cwd",
    "credential",
    "credentials",
    "private_key",
    "secret",
    "secrets",
}
SECRET_VALUE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:sk|ghp)_[A-Za-z0-9_-]{8,}|bearer\s+\S+",
    re.IGNORECASE,
)


def load(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


def walk(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def validate_projection(value: dict) -> None:
    required = {
        "schema",
        "generated_at",
        "project",
        *SECTIONS,
        "presentation",
    }
    assert required <= set(value)
    assert value["schema"] == SCHEMA_ID
    assert set(value["project"]) >= {"selection_id", "id", "swarm_id", "work_id", "snapshot"}
    assert re.fullmatch(r"[0-9a-f]{64}", value["project"]["snapshot"])
    for section in SECTIONS:
        projection = value[section]
        assert projection["status"] in {"available", "unavailable"}
        if projection["status"] == "available":
            assert "value" in projection and "reason" not in projection
        else:
            assert "value" not in projection
            assert set(projection["reason"]) >= {"code", "message"}
    assert value["presentation"]["authoritative"] is False
    lifecycle = value["lifecycle"]
    if lifecycle["status"] == "available":
        state_ids = {state["id"] for state in lifecycle["value"]["states"]}
        assert lifecycle["value"]["current_state"] in state_ids
        assert lifecycle["value"]["terminal_state"] in state_ids
    provenance = value["provenance"]
    if provenance["status"] == "available":
        for execution in provenance["value"]["executions"]:
            assert execution["session_id"]
            for field in ("runtime", "runtime_version", "provider", "model", "selection_reason"):
                item = execution[field]
                assert (item["source"] == "unavailable") == (item["value"] is None)
            fallback = execution["fallback"]
            if fallback["source"] == "unavailable":
                assert fallback["used"] is fallback["from"] is fallback["reason"] is None
            elif fallback["used"]:
                assert set(fallback["from"]) >= {"runtime", "provider", "model"}
                assert fallback["reason"]
            else:
                assert fallback["from"] is None and fallback["reason"] is None


def test_schema_is_local_resolvable_and_forward_compatible():
    schema = json.loads((ROOT / "ai-sdlc-projection-v1.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["schema"]["const"] == SCHEMA_ID
    assert schema["additionalProperties"] is True
    assert schema["$defs"]["state"]["additionalProperties"] is True
    assert "enum" not in schema["$defs"]["identifier"]
    definitions = schema["$defs"]
    for key, value in walk(schema):
        if key == "$ref":
            assert value.startswith("#/$defs/")
            assert value.removeprefix("#/$defs/") in definitions


@pytest.mark.parametrize("name", ["complete", "unavailable", "future-state"])
def test_contract_fixtures_have_required_explicit_sections(name):
    validate_projection(load(name))


def test_unavailable_fixture_never_uses_null_or_empty_object_for_missing_projection():
    fixture = load("unavailable")
    assert all(fixture[name]["status"] == "unavailable" for name in SECTIONS)
    assert all(fixture[name]["reason"]["code"].startswith("projection.") for name in SECTIONS)


def test_unknown_future_state_and_additive_fields_remain_accepted():
    fixture = load("future-state")
    validate_projection(fixture)
    lifecycle = fixture["lifecycle"]["value"]
    assert lifecycle["current_state"] == "assurance-review"
    assert lifecycle["future_lifecycle_field"]["ignored_by_v1_consumers"]
    assert "future_top_level_section" in fixture
    extended = copy.deepcopy(load("complete"))
    extended["another_future_section"] = {"status": "available", "value": {"new": True}}
    extended["lifecycle"]["value"]["states"][0]["new_hint"] = "optional"
    validate_projection(extended)


def test_missing_projection_is_invalid_instead_of_implicitly_unknown():
    fixture = load("complete")
    del fixture["provenance"]
    with pytest.raises(AssertionError):
        validate_projection(fixture)


@pytest.mark.parametrize("name", ["complete", "unavailable", "future-state"])
def test_browser_contract_contains_no_paths_credentials_or_secrets(name):
    fixture = load(name)
    for key, value in walk(fixture):
        assert key.casefold() not in FORBIDDEN_KEYS
        if isinstance(value, str):
            assert not value.startswith(("/", "file://"))
            assert re.match(r"^[A-Za-z]:[\\/]", value) is None
            assert SECRET_VALUE.search(value) is None


def test_complete_fixture_separates_source_authority_from_presentation():
    fixture = load("complete")
    assert fixture["lifecycle"]["value"]["source_schema"].startswith("agora/application/")
    assert fixture["clarifications"]["value"]["source_schema"].startswith("agora/application/")
    assert fixture["presentation"]["authoritative"] is False
    assert "construction" in fixture["presentation"]["labels"]


def test_contract_assets_are_available_through_the_package_asset_boundary():
    assert (asset_root("contracts") / "studio" / "ai-sdlc-projection-v1.schema.json").is_file()
