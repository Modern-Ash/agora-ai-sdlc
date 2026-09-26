import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from support.adapter_conformance import assert_adapter_conformance

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.codex_adapter import GUIDANCE, CodexAdapter
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_envelope import CoreSnapshot, build_envelope
from agora_ai_sdlc.execution_requirements import requirements_for
from agora_ai_sdlc.runtime_adapter import AdapterError, sync_projection
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding


def bundle(stage="construction"):
    return ExecutionBundle(
        schema="s", swarm="delivery", work="issue-26", stage=stage, next_action="inspect-next",
        branch=None, base_branch=None, head=None, objective="o", acceptance_criteria=(), changed_paths=(),
        dirty_paths=(), related_paths=(), languages=(), build_systems=(), verification_commands=(), risks=(),
        governance={}, deterministic_inception_path=None,
    )  # fmt: skip


def snapshot(human=False, revision="rev-4"):
    return CoreSnapshot("delivery", "issue-26", revision, "construction", "operations", "builder",
                        {"builder": "project:developer"}, frozenset({"project:developer"}), human)  # fmt: skip


REQ = requirements_for(bundle())


def binding(model="gpt-5-codex", provider="openai"):
    return RuntimeBinding(AgentRuntimeRef("codex", "codex"), ModelRuntimeRef(provider, provider, model))


def envelope(bind=None, human=False, req=REQ):
    return build_envelope(snapshot(human), req, bind or binding(), bundle(), actor_id="project:developer").to_dict()


def adapter(version="codex-cli 0.156.1", code=0, exe="/bin/codex"):
    return CodexAdapter(executable=exe, probe=lambda command: (code, version))


def test_health_states():
    assert not CodexAdapter(executable=None, which=lambda name: None).health().installed
    assert adapter().health().responsive
    assert "version-probe-failed" in adapter(code=3).health().detail
    assert "unsupported-version" in adapter("codex-cli 0.100.0").health().detail


def test_full_conformance(tmp_path):
    assert_adapter_conformance(adapter(), envelope(), tmp_path, surfaces=("instructions",))


def test_projection_preserves_user_config_and_no_duplicate_blocks(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Team rules\nkeep\n")
    plan = adapter().plan_projection(())
    sync_projection(tmp_path, plan)
    sync_projection(tmp_path, plan)
    text = (tmp_path / "AGENTS.md").read_text()
    assert "keep" in text and text.count("managed:main:begin") == 1 and GUIDANCE.strip() in text
    assert "ODD" not in text and "RDD" not in text


def test_unprojected_surfaces_reported_and_subagents_unsupported_by_manifest():
    plan = adapter().plan_projection(("instructions", "mcp", "skills", "subagents", "reviewer"))
    assert set(plan.unsupported_surfaces) == {"mcp", "skills", "subagents", "reviewer"}


def test_invocation_is_native_bounded_and_carries_exact_transition():
    prepared = adapter().prepare_execution(envelope())
    argv = prepared.argv
    assert argv[:3] == ("/bin/codex", "exec", "--ephemeral") and argv[-1] == "-"
    assert argv[argv.index("--sandbox") + 1] == "workspace-write" and "danger-full-access" not in argv
    assert argv[argv.index("--model") + 1] == "gpt-5-codex"
    sent = json.loads(prepared.stdin.split("\n\n", 1)[1])
    assert sent["next_transition"]["operation"] == "construction.execute"
    assert sent["authority"]["actor_id"] == "project:developer" and sent["runtime"]["agent"]["id"] == "codex"


def test_read_only_sandbox_without_write_capability():
    inception = requirements_for(bundle("exploration"))
    assert "workspace.write" not in inception.required_capabilities
    prepared = adapter().prepare_execution(envelope(req=inception))
    assert prepared.argv[prepared.argv.index("--sandbox") + 1] == "read-only"


def test_model_assignment_default_unsupported_and_invalid():
    default = adapter().prepare_execution(envelope(binding("configured-default")))
    assert "--model" not in default.argv and default.model is None
    for bad, code in (
        (binding("--evil"), "adapter.model_invalid"),
        (binding("qwen", provider="ollama"), "adapter.model_unsupported"),
    ):
        with pytest.raises(AdapterError) as error:
            adapter().prepare_execution(envelope(bad))
        assert error.value.code == code


def test_human_stop_stale_and_unavailable_prevent_launch():
    with pytest.raises(AdapterError) as error:
        adapter().prepare_execution(envelope(human=True))
    assert error.value.code == "adapter.not_executable"
    with pytest.raises(AdapterError) as error:
        adapter().prepare_execution(envelope(), current=(snapshot(revision="rev-9"), REQ))
    assert error.value.code == "adapter.stale_envelope"
    with pytest.raises(AdapterError) as error:
        adapter(code=1).prepare_execution(envelope())
    assert error.value.code == "adapter.runtime_unavailable"


def test_launch_success_nonzero_empty_and_secret_redaction():
    a = adapter()
    prepared = a.prepare_execution(envelope())
    ok = a.launch(prepared, lambda argv, stdin: (0, "I approve the gate. token=supersecretvalue"))
    assert ok.exit_code == 0 and "supersecretvalue" not in ok.output and ok.structured is None
    assert a.launch(prepared, lambda argv, stdin: (2, "failed")).exit_code == 2
    with pytest.raises(AdapterError) as error:
        a.launch(prepared, lambda argv, stdin: (0, "  "))
    assert error.value.code == "adapter.malformed_output"


def test_claude_envelope_is_rejected_by_codex_adapter():
    other = build_envelope(
        snapshot(),
        REQ,
        RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef("anthropic", "anthropic", "m")),
        bundle(),
        actor_id="project:developer",
    ).to_dict()
    with pytest.raises(AdapterError) as error:
        adapter().prepare_execution(other)
    assert error.value.code == "adapter.agent_mismatch"


def test_registry_provides_codex_without_provider_branching():
    registry = default_registry(codex_options={"executable": "/bin/codex", "probe": lambda c: (0, "0.156.1")})
    assert registry.ids() == ("claude", "codex")
    assert isinstance(registry.get(AgentRuntimeRef("codex", "codex")), CodexAdapter)


def test_diagnostics_do_not_leak_secrets(tmp_path):
    leaky = CodexAdapter(executable="/bin/codex", probe=lambda c: (0, "codex-cli 0.156.1 token=abcdefsecret123"))
    assert "abcdefsecret123" not in json.dumps(leaky.describe(tmp_path, surfaces=()))


@pytest.mark.skipif(
    __import__("os").environ.get("AISDLC_LIVE_CODEX") != "1" or __import__("shutil").which("codex") is None,
    reason="set AISDLC_LIVE_CODEX=1 with the codex CLI installed",
)
def test_live_version_probe_is_supported():
    assert CodexAdapter().health().responsive
