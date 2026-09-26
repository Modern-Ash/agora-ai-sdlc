import json

import pytest

from agora_ai_sdlc.agent_capabilities import (
    CAPABILITY_IDS,
    MANIFEST_SCHEMA,
    CapabilityError,
    build_manifest,
    manifest_for,
    registered_manifests,
)
from agora_ai_sdlc.cli import main
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef


def test_registry_covers_supported_agents_with_every_capability_explicit():
    assert [item.agent for item in registered_manifests()] == ["claude", "codex", "opencode"]
    for item in registered_manifests():
        assert tuple(item.to_dict()["capabilities"]) == CAPABILITY_IDS
        assert item.to_dict()["schema"] == MANIFEST_SCHEMA
        assert item.supports("isolated_reviewer") is False


def test_lookup_by_ref_and_digest_is_deterministic():
    ref = AgentRuntimeRef("claude", "claude-code")
    assert manifest_for(ref).digest == manifest_for("claude").digest
    assert manifest_for(ref).digest != manifest_for("codex").digest
    assert manifest_for(AgentRuntimeRef("opencode", "generic")).agent == "opencode"


def test_unknown_agent_capability_and_mismatch_fail_closed():
    with pytest.raises(CapabilityError) as error:
        manifest_for("ollama")
    assert error.value.code == "agent.unknown"
    with pytest.raises(CapabilityError) as error:
        manifest_for(AgentRuntimeRef("claude", "codex"))
    assert error.value.code == "agent.integration_mismatch"
    with pytest.raises(CapabilityError) as error:
        manifest_for("claude").supports("telepathy")
    assert error.value.code == "capability.unknown"


def test_build_manifest_rejects_unknown_missing_and_non_boolean_claims():
    full = {name: False for name in CAPABILITY_IDS}
    with pytest.raises(CapabilityError, match="unknown"):
        build_manifest("a", "b", {**full, "extra": True})
    with pytest.raises(CapabilityError, match="explicit"):
        build_manifest("a", "b", {"skills": True})
    with pytest.raises(CapabilityError, match="booleans"):
        build_manifest("a", "b", {**full, "mcp": "yes"})


def test_manifest_is_immutable():
    with pytest.raises(TypeError):
        manifest_for("claude").capabilities["mcp"] = False


def test_cli_exposes_manifests(capsys):
    assert main(["runtimes", "--capabilities"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {item["agent"] for item in payload} == {"claude", "codex", "opencode"}
    assert all(item["digest"].startswith("sha256:") for item in payload)
