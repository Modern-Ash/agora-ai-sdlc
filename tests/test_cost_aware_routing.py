from types import SimpleNamespace

import pytest
import yaml

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_policy import ExecutionPolicyError, execution_policy_for
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_execution import build_governed_runtime_plan
from agora_ai_sdlc.runtime_pool import RuntimePoolError, load_runtime_pool, select_from_runtime_pool


def discovered(runtime_id, *, ok=True, models=()):
    return RuntimeDiscovery(
        runtime_id,
        runtime_id,
        runtime_id,
        ok,
        f"/bin/{runtime_id}" if ok else None,
        ok,
        "1.0",
        True,
        "responsive" if runtime_id == "ollama" and ok else None,
        None,
        tuple(models),
    )


def project(root, *, paid=False, frontier=False):
    target = root / "ai-sdlc" / "project.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(
        yaml.safe_dump(
            {
                "routing": {
                    "profile": "cheap-first",
                    "allow_paid_auto": paid,
                    "allow_frontier_auto": frontier,
                    "candidates": [
                        {
                            "tier": "local",
                            "agent": "opencode",
                            "model": "ollama/qwen3-coder:latest",
                        },
                        {
                            "tier": "free",
                            "agent": "opencode",
                            "model": "opencode/free-coder",
                        },
                        {
                            "tier": "paid-efficient",
                            "agent": "codex",
                            "model": "openai/configured-efficient",
                        },
                        {
                            "tier": "paid-standard",
                            "agent": "claude",
                            "model": "anthropic/configured-standard",
                        },
                        {
                            "tier": "frontier",
                            "agent": "codex",
                            "model": "openai/configured-frontier",
                        },
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def availability(*, local=True, free=True, codex=True, claude=True):
    return {
        "opencode": discovered("opencode", ok=local or free),
        "ollama": discovered(
            "ollama",
            ok=local,
            models=("qwen3-coder:latest",) if local else (),
        ),
        "codex": discovered("codex", ok=codex),
        "claude": discovered("claude", ok=claude),
    }


def bundle():
    return ExecutionBundle(
        schema="s",
        swarm="delivery",
        work="issue-x",
        stage="construction",
        next_action="inspect-next",
        branch=None,
        base_branch=None,
        head=None,
        objective="o",
        acceptance_criteria=(),
        changed_paths=(),
        dirty_paths=(),
        related_paths=(),
        languages=(),
        build_systems=(),
        verification_commands=(),
        risks=(),
        governance={},
        deterministic_inception_path=None,
    )


def test_execution_policy_uses_progressive_cost_ceiling():
    local = execution_policy_for(requirements_for_activity("construction.implementation", tier="local"))
    standard = execution_policy_for(requirements_for_activity("construction.implementation", tier="standard"))
    frontier = execution_policy_for(requirements_for_activity("construction.implementation", tier="frontier"))

    assert local.max_automatic_tier == "paid-efficient"
    assert standard.max_automatic_tier == "paid-standard"
    assert frontier.max_automatic_tier == "frontier"
    assert local.preferred_tier == standard.preferred_tier == frontier.preferred_tier == "local"


def test_human_policy_is_not_executable():
    with pytest.raises(ExecutionPolicyError, match="human-authority"):
        execution_policy_for(requirements_for_activity("human.authority", tier="human"))


def test_pool_prefers_local_even_when_paid_models_are_available(tmp_path):
    project(tmp_path, paid=True, frontier=True)
    req = requirements_for_activity("construction.implementation", tier="local")

    selected = select_from_runtime_pool(tmp_path, req, availability=availability())

    assert selected is not None
    assert selected.tier == "local"
    assert selected.binding.agent.id == "opencode"
    assert selected.binding.model is not None
    assert selected.binding.model.provider == "ollama"
    assert selected.binding.model.model == "qwen3-coder:latest"


def test_paid_fallback_requires_explicit_project_opt_in(tmp_path):
    project(tmp_path, paid=False)
    req = requirements_for_activity("construction.implementation", tier="local")

    with pytest.raises(RuntimePoolError, match="routing.blocked"):
        select_from_runtime_pool(
            tmp_path,
            req,
            availability=availability(local=False, free=False, codex=True),
        )


def test_paid_efficient_is_used_before_more_expensive_paid_models(tmp_path):
    project(tmp_path, paid=True, frontier=True)
    req = requirements_for_activity("construction.implementation", tier="standard")

    selected = select_from_runtime_pool(
        tmp_path,
        req,
        availability=availability(local=False, free=False, codex=True, claude=True),
    )

    assert selected is not None
    assert selected.tier == "paid-efficient"
    assert selected.binding.agent.id == "codex"
    assert selected.binding.model is not None
    assert selected.binding.model.model == "configured-efficient"


def test_frontier_is_never_automatic_without_separate_opt_in(tmp_path):
    project(tmp_path, paid=True, frontier=False)
    req = requirements_for_activity("construction.implementation", tier="frontier")

    with pytest.raises(RuntimePoolError, match="routing.blocked"):
        select_from_runtime_pool(
            tmp_path,
            req,
            availability=availability(local=False, free=False, codex=False, claude=False),
        )


def test_pool_is_opt_in(tmp_path):
    assert load_runtime_pool(tmp_path) is None


class FakeWorkspace:
    def show_swarm(self, swarm):
        return SimpleNamespace(assignments={"builder": "project:developer"})

    def list_actors(self):
        return [SimpleNamespace(id="developer", reference="project:developer")]

    def work_inspection_read_set_sha256(self, swarm, work):
        return "rev-1"


class FakeAdapter:
    def prepare_execution(self, envelope, current=None):
        return envelope


class FakeRegistry:
    def get(self, agent):
        return FakeAdapter()


def decision():
    return SimpleNamespace(
        swarm="delivery",
        work="issue-x",
        state="construction",
        target="operations",
        role="builder",
        actor="project:developer",
        missing_approvals=(),
    )


def test_governed_plan_auto_selects_pool_but_explicit_runtime_is_override(tmp_path, monkeypatch):
    project(tmp_path, paid=True, frontier=True)
    monkeypatch.setattr("agora_ai_sdlc.runtime_execution.default_registry", lambda root: FakeRegistry())
    observed = availability()

    automatic = build_governed_runtime_plan(
        tmp_path,
        decision=decision(),
        bundle=bundle(),
        runtime_id=None,
        model=None,
        availability=observed,
        workspace=FakeWorkspace(),
        actor="project:developer",
    )
    assert automatic.binding.agent.id == "opencode"
    assert automatic.execution_tier == "local"
    assert automatic.envelope.context["routing"]["tier"] == "local"

    explicit = build_governed_runtime_plan(
        tmp_path,
        decision=decision(),
        bundle=bundle(),
        runtime_id="codex",
        model="configured-efficient",
        availability=observed,
        workspace=FakeWorkspace(),
        actor="project:developer",
    )
    assert explicit.binding.agent.id == "codex"
    assert explicit.execution_tier is None
