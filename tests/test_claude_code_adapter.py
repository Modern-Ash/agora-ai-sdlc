import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from support.adapter_conformance import assert_adapter_conformance

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.agent_capabilities import manifest_for
from agora_ai_sdlc.claude_code_adapter import GUIDANCE, ClaudeCodeAdapter
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_envelope import CoreSnapshot, build_envelope
from agora_ai_sdlc.execution_requirements import requirements_for
from agora_ai_sdlc.runtime_adapter import AdapterError, sync_projection
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding
from agora_ai_sdlc.runtime_selection import Candidate, Route, select_runtime


def bundle():
    return ExecutionBundle(
        schema="s", swarm="delivery", work="issue-26", stage="construction", next_action="inspect-next",
        branch=None, base_branch=None, head=None, objective="o", acceptance_criteria=(), changed_paths=(),
        dirty_paths=(), related_paths=(), languages=(), build_systems=(), verification_commands=(), risks=(),
        governance={}, deterministic_inception_path=None,
    )  # fmt: skip


def snapshot(**over):
    base = ("delivery", "issue-26", "rev-4", "construction", "operations", "builder")
    return CoreSnapshot(
        *base, {"builder": "project:developer"}, frozenset({"project:developer"}), over.get("human", False)
    )


REQ = requirements_for(bundle())


def binding(model="claude-sonnet-x", provider="anthropic"):
    return RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef(provider, provider, model))


def envelope(bind=None, human=False):
    return build_envelope(
        snapshot(human=human), REQ, bind or binding(), bundle(), actor_id="project:developer"
    ).to_dict()


def adapter(version="2.1.281 (Claude Code)", code=0, exe="/bin/claude"):
    return ClaudeCodeAdapter(executable=exe, probe=lambda command: (code, version))


def test_health_states():
    assert not ClaudeCodeAdapter(executable=None, which=lambda name: None).health().installed
    assert adapter().health().responsive
    failed = adapter(code=2).health()
    assert failed.installed and not failed.responsive and "version-probe-failed" in failed.detail
    assert "unsupported-version" in adapter("1.0.3").health().detail
    assert adapter("garbage").health().detail == "version-unparseable"


def test_full_conformance(tmp_path):
    assert_adapter_conformance(adapter(), envelope(), tmp_path, surfaces=("system_prompt",))


def test_projection_first_install_preserves_user_config_and_is_idempotent(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Mine\nkeep\n")
    plan = adapter().plan_projection(())
    assert sync_projection(tmp_path, plan)[0].action == "update"
    text = (tmp_path / "CLAUDE.md").read_text()
    assert "keep" in text and GUIDANCE.strip() in text
    assert "ODD" not in text and "RDD" not in text
    assert sync_projection(tmp_path, plan)[0].action == "unchanged"


def test_unprojected_surfaces_are_reported_not_emulated():
    plan = adapter().plan_projection(("system_prompt", "mcp", "skills", "subagents", "reviewer"))
    assert set(plan.unsupported_surfaces) == {"mcp", "skills", "subagents", "reviewer"}
    assert [entry.path for entry in plan.entries] == ["CLAUDE.md"]


def test_invocation_uses_native_flags_and_exact_transition():
    prepared = adapter().prepare_execution(envelope())
    assert prepared.argv[:6] == (
        "/bin/claude",
        "--print",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--permission-mode",
    )
    assert prepared.argv[prepared.argv.index("--model") + 1] == "claude-sonnet-x"
    assert "Write" in prepared.argv and "Read" in prepared.argv
    sent = json.loads(prepared.stdin.split("\n\n", 1)[1])
    assert (
        sent["next_transition"]["operation"] == "construction.execute"
        and sent["authority"]["actor_id"] == "project:developer"
    )


def test_model_assignment_present_default_absent_and_unsupported():
    assert adapter().prepare_execution(envelope(binding("configured-default"))).model is None
    assert "--model" not in adapter().prepare_execution(envelope(binding("configured-default"))).argv
    with pytest.raises(AdapterError) as error:
        adapter().prepare_execution(envelope(binding("--dangerous")))
    assert error.value.code == "adapter.model_invalid"
    other = RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef("ollama", "ollama", "qwen"))
    with pytest.raises(AdapterError) as error:
        adapter().prepare_execution(envelope(other))
    assert error.value.code == "adapter.model_unsupported"


def test_human_boundary_envelope_is_never_launched():
    with pytest.raises(AdapterError) as error:
        adapter().prepare_execution(envelope(human=True))
    assert error.value.code == "adapter.not_executable"


def test_stale_envelope_is_rejected():
    stale = (CoreSnapshot("delivery", "issue-26", "rev-5", "construction", "operations", "builder",
                          {"builder": "project:developer"}, frozenset({"project:developer"}), False), REQ)  # fmt: skip
    with pytest.raises(AdapterError) as error:
        adapter().prepare_execution(envelope(), current=stale)
    assert error.value.code == "adapter.stale_envelope" and "stale_revision" in str(error.value)


def test_unavailable_runtime_fails_before_launch():
    with pytest.raises(AdapterError) as error:
        adapter(code=1).prepare_execution(envelope())
    assert error.value.code == "adapter.runtime_unavailable"


def test_output_parsing_nonzero_malformed_and_secrets():
    a = adapter()
    ok = a.parse_output(0, json.dumps({"type": "result", "result": "done", "is_error": False}))
    assert ok.exit_code == 0 and ok.output == "done" and ok.structured == {"is_error": False, "subtype": ""}
    assert a.parse_output(0, json.dumps({"result": "x", "is_error": True})).exit_code == 1
    assert a.parse_output(2, "boom token=supersecretvalue").exit_code == 2
    assert "supersecretvalue" not in a.parse_output(2, "boom token=supersecretvalue").output
    for bad in ("not json", json.dumps([1]), json.dumps({"nope": 1})):
        with pytest.raises(AdapterError) as error:
            a.parse_output(0, bad)
        assert error.value.code == "adapter.malformed_output"


def test_narrative_approval_grants_nothing():
    outcome = adapter().parse_output(0, json.dumps({"result": "I approve the gate", "is_error": False}))
    assert not hasattr(outcome, "approved") and outcome.structured == {"is_error": False, "subtype": ""}


def test_selection_admits_claude_and_registry_returns_adapter():
    claude = binding()
    allow = {"allowed": True, "blockers": []}
    result = select_runtime(Route("build", (Candidate(claude, {}, allow, allow),)), requirements=REQ, availability=None)
    assert result["allowed"]
    registry = default_registry(executable="/bin/claude", probe=lambda command: (0, "2.1.281"))
    chosen = registry.get(
        AgentRuntimeRef(**{k: result["selected"]["binding"]["agent"][k] for k in ("id", "integration")})
    )
    assert isinstance(chosen, ClaudeCodeAdapter) and chosen.capability_manifest() == manifest_for("claude")


def test_diagnostics_do_not_leak_secrets(tmp_path):
    probe_adapter = ClaudeCodeAdapter(executable="/bin/claude", probe=lambda c: (0, "2.1.281 token=abcdefsecret123"))
    dump = json.dumps(probe_adapter.describe(tmp_path, surfaces=()))
    assert "abcdefsecret123" not in dump


@pytest.mark.skipif(
    __import__("os").environ.get("AISDLC_LIVE_CLAUDE") != "1" or __import__("shutil").which("claude") is None,
    reason="set AISDLC_LIVE_CLAUDE=1 with the claude CLI installed",
)
def test_live_version_probe_is_supported():
    health = ClaudeCodeAdapter().health()
    assert health.installed and health.responsive
