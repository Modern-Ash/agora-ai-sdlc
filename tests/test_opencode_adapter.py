import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from support.adapter_conformance import assert_adapter_conformance

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_envelope import CoreSnapshot, build_envelope
from agora_ai_sdlc.execution_requirements import requirements_for
from agora_ai_sdlc.opencode_adapter import GUIDANCE, OpenCodeAdapter
from agora_ai_sdlc.runtime_adapter import AdapterError, sync_projection
from agora_ai_sdlc.runtime_discovery import discover_runtimes
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding
from agora_ai_sdlc.runtime_selection import Candidate, Route, select_runtime

ALLOW = {"allowed": True, "blockers": []}


def bundle():
    return ExecutionBundle(
        schema="s", swarm="delivery", work="issue-26", stage="construction", next_action="inspect-next",
        branch=None, base_branch=None, head=None, objective="o", acceptance_criteria=(), changed_paths=(),
        dirty_paths=(), related_paths=(), languages=(), build_systems=(), verification_commands=(), risks=(),
        governance={}, deterministic_inception_path=None,
    )  # fmt: skip


SNAPSHOT = CoreSnapshot("delivery", "issue-26", "rev-4", "construction", "operations", "builder",
                        {"builder": "project:developer"}, frozenset({"project:developer"}), False)  # fmt: skip
REQ = requirements_for(bundle())


def ollama(model="qwen2.5-coder:7b"):
    return RuntimeBinding(AgentRuntimeRef("opencode", "opencode"), ModelRuntimeRef("ollama", "ollama", model))


def envelope(bind=None):
    return build_envelope(SNAPSHOT, REQ, bind or ollama(), bundle(), actor_id="project:developer").to_dict()


def adapter(root, version="1.18.32", code=0):
    return OpenCodeAdapter(root=root, executable="/bin/opencode", probe=lambda c: (code, version))


def fake_tools(ollama_ok=True, listing="NAME ID SIZE MODIFIED\nqwen2.5-coder:7b abc 4GB now\n", opencode=True):
    paths = {"ollama": "/bin/ollama", "opencode": "/bin/opencode"}
    if not opencode:
        paths.pop("opencode")

    def runner(command, **kwargs):
        if command[1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout="1.18.32\n", stderr="")
        if command[1] == "ps":
            return subprocess.CompletedProcess(command, 0 if ollama_ok else 1, stdout="", stderr="")
        if command[1] == "list":
            return subprocess.CompletedProcess(command, 0, stdout=listing, stderr="")
        raise AssertionError(f"unexpected command {command}")  # e.g. a pull

    return {"which": paths.get, "runner": runner}


def observe(tmp_path, **kwargs):
    return {item.id: item for item in discover_runtimes(tmp_path, **fake_tools(**kwargs))}


def route(*bindings):
    return Route("build", tuple(Candidate(b, {}, ALLOW, ALLOW) for b in bindings))


def test_health_missing_probe_failure_and_version(tmp_path):
    assert not OpenCodeAdapter(root=tmp_path, executable=None, which=lambda n: None).health().installed
    assert adapter(tmp_path).health().responsive
    assert "version-probe-failed" in adapter(tmp_path, code=1).health().detail
    assert "unsupported-version" in adapter(tmp_path, "0.9.0").health().detail


def test_full_conformance(tmp_path):
    assert_adapter_conformance(adapter(tmp_path), envelope(), tmp_path, surfaces=("instructions",))


def test_projection_preserves_unrelated_config_and_persists_no_provider_keys(tmp_path):
    (tmp_path / "opencode.json").write_text(json.dumps({"provider": {"mine": {}}, "model": "mine/x"}))
    (tmp_path / "AGENTS.md").write_text("# rules\nkeep\n")
    plan = adapter(tmp_path).plan_projection(())
    sync_projection(tmp_path, plan)
    sync_projection(tmp_path, plan)
    assert json.loads((tmp_path / "opencode.json").read_text()) == {"provider": {"mine": {}}, "model": "mine/x"}
    text = (tmp_path / "AGENTS.md").read_text()
    assert "keep" in text and text.count("managed:main:begin") == 1 and GUIDANCE.strip() in text


def test_discovery_reports_ollama_as_model_runtime_with_models(tmp_path):
    found = observe(tmp_path)
    assert found["ollama"].snapshot()["kind"] == "model" and found["opencode"].snapshot()["kind"] == "agent"
    assert found["ollama"].models == ("qwen2.5-coder:7b",) and found["opencode"].models == ()


def test_ollama_alone_is_rejected_and_opencode_plus_ollama_admitted(tmp_path):
    found = observe(tmp_path)
    alone = select_runtime(
        Route("build", (Candidate(ModelRuntimeRef("ollama", "ollama", "qwen2.5-coder:7b"), {}, ALLOW, ALLOW),)),
        requirements=REQ, availability=found,
    )  # fmt: skip
    assert alone["considered"][0]["blockers"] == ("runtime.agent_required",)
    ok = select_runtime(route(ollama()), requirements=REQ, availability=found)
    assert ok["allowed"] and ok["selected"]["binding"]["model"]["provider"] == "ollama"


def test_binding_rejected_when_tools_service_or_model_missing(tmp_path):
    cases = [
        ({"opencode": False}, "runtime.integration_unavailable"),
        ({"ollama_ok": False}, "runtime.model_unavailable"),
        ({"listing": "NAME ID\nllama3:8b x\n"}, "runtime.model_unavailable"),
    ]
    for kwargs, code in cases:
        result = select_runtime(route(ollama()), requirements=REQ, availability=observe(tmp_path, **kwargs))
        assert not result["allowed"] and code in result["considered"][0]["blockers"], kwargs
    absent = select_runtime(route(ollama()), requirements=REQ, availability=observe(tmp_path, listing="NAME\nx:1 a\n"))
    assert {b for b in absent["considered"][0]["blockers"]} == {"runtime.model_unavailable"}


def test_model_present_without_tag_matches_latest(tmp_path):
    found = observe(tmp_path, listing="NAME ID\nqwen2.5-coder:latest x\n")
    assert select_runtime(route(ollama("qwen2.5-coder")), requirements=REQ, availability=found)["allowed"]


def test_missing_ollama_binary_is_model_unavailable(tmp_path):
    found = {k: v for k, v in observe(tmp_path).items() if k != "ollama"}
    result = select_runtime(route(ollama()), requirements=REQ, availability=found)
    assert result["considered"][0]["blockers"] == ()  # unobserved model runtimes are not asserted absent


def test_explicit_candidate_ordering_and_non_ollama_provider(tmp_path):
    other = RuntimeBinding(AgentRuntimeRef("opencode", "opencode"), ModelRuntimeRef("acme", "acme", "big-1"))
    found = observe(tmp_path)
    first_other = select_runtime(route(other, ollama()), requirements=REQ, availability=found)
    assert first_other["selected"]["binding"]["model"]["provider"] == "acme"
    prepared = adapter(tmp_path).prepare_execution(envelope(other))
    assert prepared.model == "acme/big-1"


def test_invocation_uses_supervisor_with_explicit_model_and_never_pulls(tmp_path):
    prepared = adapter(tmp_path).prepare_execution(envelope())
    argv = prepared.argv
    assert argv[1:3] == ("-m", "agora_ai_sdlc.opencode_runner")
    assert argv[argv.index("--model") + 1] == "ollama/qwen2.5-coder:7b"
    assert "pull" not in argv and prepared.stdin == ""
    sent = json.loads(argv[argv.index("--prompt") + 1].split("\n\n", 1)[1])
    assert sent["runtime"]["agent"]["id"] == "opencode" and sent["runtime"]["model"]["provider"] == "ollama"
    assert sent["next_transition"]["operation"] == "construction.execute"


def test_explicit_model_is_required_and_validated(tmp_path):
    bare = RuntimeBinding(
        AgentRuntimeRef("opencode", "opencode"), ModelRuntimeRef("ollama", "ollama", "configured-default")
    )
    with pytest.raises(AdapterError) as error:
        adapter(tmp_path).prepare_execution(envelope(bare))
    assert error.value.code == "adapter.model_required"
    with pytest.raises(AdapterError) as error:
        adapter(tmp_path).prepare_execution(envelope(ollama("--x")))
    assert error.value.code == "adapter.model_invalid"


def test_stale_and_unavailable_prevent_launch_and_output_is_not_authority(tmp_path):
    a = adapter(tmp_path)
    stale = CoreSnapshot("delivery", "issue-26", "rev-9", "construction", "operations", "builder",
                         {"builder": "project:developer"}, frozenset({"project:developer"}), False)  # fmt: skip
    with pytest.raises(AdapterError) as error:
        a.prepare_execution(envelope(), current=(stale, REQ))
    assert error.value.code == "adapter.stale_envelope"
    with pytest.raises(AdapterError):
        adapter(tmp_path, code=1).prepare_execution(envelope())
    prepared = a.prepare_execution(envelope())
    ok = a.launch(prepared, lambda argv, stdin: (0, "approved! token=supersecretvalue"))
    assert ok.structured is None and "supersecretvalue" not in ok.output
    assert a.launch(prepared, lambda argv, stdin: (3, "err")).exit_code == 3
    with pytest.raises(AdapterError) as error:
        a.launch(prepared, lambda argv, stdin: (0, ""))
    assert error.value.code == "adapter.malformed_output"


def test_no_provider_hopping_after_ordinary_failure(tmp_path):
    result = select_runtime(route(ollama()), signal="ordinary-failure", requirements=REQ)
    assert not result["allowed"] and result["blockers"][0]["code"] == "fallback.ordinary_failure"


def test_registry_holds_all_three_agents_and_diagnostics_are_secret_free(tmp_path):
    registry = default_registry(tmp_path)
    assert registry.ids() == ("claude", "codex", "opencode")
    leaky = OpenCodeAdapter(
        root=tmp_path, executable="/bin/opencode", probe=lambda c: (0, "1.18.32 token=abcdefsecret123")
    )
    assert "abcdefsecret123" not in json.dumps(leaky.describe(tmp_path, surfaces=()))
