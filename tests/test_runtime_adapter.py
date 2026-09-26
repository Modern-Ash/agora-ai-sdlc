import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from support.adapter_conformance import assert_adapter_conformance

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_envelope import CoreSnapshot, build_envelope
from agora_ai_sdlc.execution_requirements import requirements_for
from agora_ai_sdlc.runtime_adapter import (
    AdapterError,
    AdapterRegistry,
    Health,
    PreparedExecution,
    ProjectionEntry,
    ProjectionPlan,
    RuntimeAdapter,
    plan_sync,
    sanitize,
    supported_surfaces,
    sync_projection,
)
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding


def bundle():
    return ExecutionBundle(
        schema="s", swarm="delivery", work="issue-26", stage="construction", next_action="inspect-next",
        branch=None, base_branch=None, head=None, objective="o", acceptance_criteria=(), changed_paths=(),
        dirty_paths=(), related_paths=(), languages=(), build_systems=(), verification_commands=(), risks=(),
        governance={}, deterministic_inception_path=None,
    )  # fmt: skip


SNAPSHOT = CoreSnapshot(
    "delivery", "issue-26", "rev-4", "construction", "operations", "builder",
    {"builder": "project:developer"}, frozenset({"project:developer"}), False,
)  # fmt: skip
BINDING = RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef("anthropic", "anthropic", "m1"))


def envelope():
    return build_envelope(
        SNAPSHOT, requirements_for(bundle()), BINDING, bundle(), actor_id="project:developer"
    ).to_dict()


class FakeAdapter(RuntimeAdapter):
    integration_id = "claude"

    def health(self):
        return Health(True, True, "token=abc123secretvalue")

    def plan_projection(self, surfaces):
        _, missing = supported_surfaces(self.capability_manifest(), tuple(surfaces))
        entries = [
            ProjectionEntry("CLAUDE.md", "text_block", "system_prompt", content="Follow AGENTS.md."),
            ProjectionEntry(".mcp.json", "json_keys", "mcp", keys={"mcpServers": {"agora": {"command": "agora"}}}),
        ]
        return ProjectionPlan("claude", tuple(entries), unsupported_surfaces=missing)

    def render_invocation(self, env):
        return PreparedExecution(
            "claude", env.to_dict()["digest"], env.operation, env.arguments, ("claude", "--print"), env.to_json()
        )


class LyingAdapter(FakeAdapter):
    @property
    def advertised_capabilities(self):
        return frozenset({"isolated_reviewer"})


class AlteringAdapter(FakeAdapter):
    def render_invocation(self, env):
        prepared = super().render_invocation(env)
        return PreparedExecution(
            "claude", prepared.envelope_digest, "lifecycle.transition", prepared.arguments, prepared.argv, ""
        )


def test_registry_get_missing_duplicate_unknown_and_parity(tmp_path):
    registry = AdapterRegistry()
    adapter = FakeAdapter()
    registry.register(adapter)
    assert registry.get("claude") is adapter and registry.get(AgentRuntimeRef("claude", "claude-code")) is adapter
    with pytest.raises(AdapterError) as error:
        registry.register(FakeAdapter())
    assert error.value.code == "adapter.duplicate"
    with pytest.raises(AdapterError) as error:
        registry.get("codex")
    assert error.value.code == "adapter.missing"
    with pytest.raises(AdapterError) as error:
        registry.get("ollama")
    assert error.value.code == "adapter.unknown"
    with pytest.raises(AdapterError) as error:
        AdapterRegistry().register(LyingAdapter())
    assert error.value.code == "adapter.capability_parity"


def test_full_conformance(tmp_path):
    assert_adapter_conformance(FakeAdapter(), envelope(), tmp_path, surfaces=("system_prompt", "mcp"))


def test_dry_run_writes_nothing(tmp_path):
    plan = FakeAdapter().plan_projection(())
    assert [a.action for a in sync_projection(tmp_path, plan, dry_run=True)] == ["create", "create"]
    assert list(tmp_path.iterdir()) == []


def test_unmanaged_config_survives_and_backup_precedes_replacement(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# My notes\n\nkeep me\n")
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"old": {}}, "theme": "dark"}))
    plan = FakeAdapter().plan_projection(())
    actions = sync_projection(tmp_path, plan)
    assert all(a.action == "update" and a.backup for a in actions)
    text = (tmp_path / "CLAUDE.md").read_text()
    assert "keep me" in text and "Follow AGENTS.md." in text
    data = json.loads((tmp_path / ".mcp.json").read_text())
    assert data["theme"] == "dark" and "agora" in data["mcpServers"]
    backups = list((tmp_path / ".agora/ai-sdlc/backups/claude").iterdir())
    assert len(backups) == 2 and any("keep me" in b.read_text() for b in backups)
    assert all(a.action == "unchanged" for a in sync_projection(tmp_path, plan))


def test_managed_block_is_replaced_not_duplicated(tmp_path):
    entry = lambda content: ProjectionPlan(
        "x", (ProjectionEntry("A.md", "text_block", "instructions", content=content),)
    )
    sync_projection(tmp_path, entry("one"))
    sync_projection(tmp_path, entry("two"))
    text = (tmp_path / "A.md").read_text()
    assert "two" in text and "one" not in text and text.count("managed:main:begin") == 1


def test_unsafe_paths_secrets_and_bad_json_fail_closed(tmp_path):
    for path in ("../evil.md", "/abs.md"):
        with pytest.raises(AdapterError) as error:
            plan_sync(
                tmp_path, ProjectionPlan("x", (ProjectionEntry(path, "text_block", "instructions", content="a"),))
            )
        assert error.value.code == "projection.path"
    with pytest.raises(AdapterError) as error:
        plan_sync(
            tmp_path,
            ProjectionPlan(
                "x", (ProjectionEntry("A.md", "text_block", "instructions", content="api_key=sk-abcdef123456"),)
            ),
        )
    assert error.value.code == "projection.content"
    (tmp_path / "bad.json").write_text("{not json")
    with pytest.raises(AdapterError) as error:
        plan_sync(tmp_path, ProjectionPlan("x", (ProjectionEntry("bad.json", "json_keys", "mcp", keys={"a": 1}),)))
    assert error.value.code == "projection.unparseable" and (tmp_path / "bad.json").read_text() == "{not json"


def test_describe_is_readonly_and_redacts_secrets(tmp_path):
    described = FakeAdapter().describe(tmp_path, surfaces=("subagents", "reviewer"), envelope=envelope())
    assert described["unsupported_surfaces"] == ["reviewer"]
    assert described["model_binding"]["model"]["model"] == "m1"
    assert "abc123secretvalue" not in json.dumps(described) and list(tmp_path.iterdir()) == []
    assert sanitize("Bearer abcdefghijklmnop") == "[redacted]"


def test_unknown_surface_fails_closed():
    with pytest.raises(AdapterError) as error:
        supported_surfaces(FakeAdapter().capability_manifest(), ("telepathy",))
    assert error.value.code == "projection.unknown_surface"


def test_transport_cannot_alter_transition_or_run_stop_envelopes():
    with pytest.raises(AdapterError) as error:
        AlteringAdapter().prepare_execution(envelope())
    assert error.value.code == "adapter.transition_altered"
    stop = build_envelope(
        CoreSnapshot("delivery", "issue-26", "rev-4", "construction", None, "builder",
                     {"builder": "project:developer"}, frozenset({"project:developer"}), True),
        requirements_for(bundle()), BINDING, bundle(), actor_id="project:developer",
    ).to_dict()  # fmt: skip
    with pytest.raises(AdapterError) as error:
        FakeAdapter().prepare_execution(stop)
    assert error.value.code == "adapter.not_executable"


def test_wrong_agent_envelope_is_rejected():
    codex = RuntimeBinding(AgentRuntimeRef("codex", "codex"), ModelRuntimeRef("openai", "openai", "m"))
    payload = build_envelope(
        SNAPSHOT, requirements_for(bundle()), codex, bundle(), actor_id="project:developer"
    ).to_dict()
    with pytest.raises(AdapterError) as error:
        FakeAdapter().prepare_execution(payload)
    assert error.value.code == "adapter.agent_mismatch"


def test_launch_returns_sanitized_outcome_without_core_mutation():
    adapter = FakeAdapter()
    prepared = adapter.prepare_execution(envelope())
    outcome = adapter.launch(prepared, lambda argv, stdin: (0, "done token=supersecretvalue"))
    assert outcome.exit_code == 0 and "supersecretvalue" not in outcome.output
