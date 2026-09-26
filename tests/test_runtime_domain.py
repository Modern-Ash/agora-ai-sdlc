import pytest

from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, agent_runtimes, model_runtimes
from agora_ai_sdlc.runtime_domain import (
    BINDING_SCHEMA,
    AgentRuntimeRef,
    ModelRuntimeRef,
    RuntimeBinding,
    RuntimeKind,
    RuntimeNormalizationError,
    normalize_runtime,
)
from agora_ai_sdlc.runtime_selection import Candidate, Route, RuntimeRef, select_runtime

ALLOW = {"allowed": True, "blockers": []}


def test_legacy_v1_normalizes_deterministically():
    legacy = {"id": "opencode", "integration": "opencode", "provider": "ollama", "model": "qwen"}
    binding = normalize_runtime(legacy)
    assert binding == RuntimeBinding(
        agent=AgentRuntimeRef("opencode", "opencode"),
        model=ModelRuntimeRef("ollama", "ollama", "qwen"),
    )
    assert normalize_runtime(legacy) == binding
    assert binding.to_dict()["schema"] == BINDING_SCHEMA
    assert binding.to_legacy() == legacy


def test_v2_mapping_round_trips():
    entry = {
        "agent": {"id": "claude", "integration": "claude-code"},
        "model": {"provider": "anthropic", "model": "configured-default"},
    }
    binding = normalize_runtime(entry)
    assert binding.agent.integration == "claude-code"
    assert binding.model == ModelRuntimeRef("anthropic", "anthropic", "configured-default")
    assert normalize_runtime({"agent": {"id": "codex", "integration": "codex"}, "model": None}).model is None


@pytest.mark.parametrize(
    ("entry", "code"),
    [
        (
            {"id": "ollama", "integration": "generic", "provider": "ollama", "model": "q"},
            "runtime.legacy_model_runtime_as_agent",
        ),
        (
            {"id": "x", "integration": "ollama", "provider": "ollama", "model": "q"},
            "runtime.legacy_model_runtime_as_agent",
        ),
        ({"id": "", "integration": "codex"}, "runtime.legacy_missing_id"),
        ({"id": "x", "integration": ""}, "runtime.legacy_missing_integration"),
        ({"id": "x", "integration": "codex", "provider": "openai"}, "runtime.legacy_partial_model"),
        ({"agent": {"id": "ollama", "integration": "generic"}}, "runtime.model_runtime_as_agent"),
        ({"agent": {"id": "a"}}, "runtime.agent_incomplete"),
        ({"agent": {"id": "a", "integration": "b"}, "model": {"provider": "p"}}, "runtime.model_incomplete"),
    ],
)
def test_ambiguous_entries_fail_closed_with_typed_diagnostic(entry, code):
    with pytest.raises(RuntimeNormalizationError) as error:
        normalize_runtime(entry)
    assert error.value.code == code
    assert error.value.diagnostic()["code"] == code


def _discovery(runtime_id):
    return RuntimeDiscovery(runtime_id, runtime_id, runtime_id, True, "/bin/x", True, "1", False)


def test_discovery_separates_agent_and_model_runtimes():
    found = tuple(_discovery(item) for item in ("codex", "claude", "opencode", "ollama"))
    assert [item.id for item in agent_runtimes(found)] == ["codex", "claude", "opencode"]
    assert [item.id for item in model_runtimes(found)] == ["ollama"]
    assert found[3].snapshot()["kind"] == RuntimeKind.MODEL.value
    assert found[0].snapshot()["kind"] == RuntimeKind.AGENT.value


def test_selection_accepts_binding_and_exposes_it():
    binding = normalize_runtime({"id": "opencode", "integration": "opencode", "provider": "ollama", "model": "qwen"})
    legacy = RuntimeRef("opencode", "opencode", "ollama", "qwen")
    results = [select_runtime(Route("build", (Candidate(runtime, {}, ALLOW, ALLOW),))) for runtime in (binding, legacy)]
    assert results[0]["selected"] == results[1]["selected"]
    assert results[0]["selected"]["binding"]["agent"]["id"] == "opencode"
    assert results[0]["selected"]["id"] == "opencode"
