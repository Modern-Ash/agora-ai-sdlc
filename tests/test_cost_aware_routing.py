from types import SimpleNamespace

import pytest
import yaml

from agora_ai_sdlc.advisory_planner import run_advisory_planner
from agora_ai_sdlc.economic_telemetry import record_economic_event, summarize_economics
from agora_ai_sdlc.escalation import build_escalation_package, persist_escalation_package, recommend_escalation
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_policy import ExecutionPolicyError, execution_policy_for
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.repair_advice import build_repair_advice, render_executor_handback
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding
from agora_ai_sdlc.runtime_execution import build_governed_runtime_plan
from agora_ai_sdlc.runtime_pool import RuntimePoolError, load_runtime_pool, select_from_runtime_pool
from agora_ai_sdlc.runtime_selection import Budget


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


def test_tier_call_limit_blocks_repeated_paid_selection(tmp_path):
    project(tmp_path, paid=True)
    payload = yaml.safe_load((tmp_path / "ai-sdlc" / "project.yaml").read_text(encoding="utf-8"))
    payload["routing"]["tier_call_limits"] = {"paid-efficient": 1}
    (tmp_path / "ai-sdlc" / "project.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    req = requirements_for_activity("construction.implementation", tier="standard")
    observed = availability(local=False, free=False, codex=True, claude=True)

    first = select_from_runtime_pool(tmp_path, req, availability=observed, work="issue-x")
    assert first is not None and first.tier == "paid-efficient"
    record_economic_event(
        tmp_path,
        work="issue-x",
        kind="runtime-selected",
        tier="paid-efficient",
        agent="codex",
        model="configured-efficient",
    )

    second = select_from_runtime_pool(tmp_path, req, availability=observed, work="issue-x")
    assert second is not None
    assert second.tier == "paid-standard"
    assert second.binding.agent.id == "claude"


def test_escalation_package_is_bounded_and_planner_selection_is_more_expensive(tmp_path):
    project(tmp_path, paid=True)
    req = requirements_for_activity("construction.implementation", tier="standard")
    failed = load_runtime_pool(tmp_path).candidates[0].binding
    package = build_escalation_package(
        swarm="delivery",
        work="issue-x",
        requirements=req,
        failed_tier="local",
        failed_binding=failed,
        attempts=3,
        diagnostic="x" * 7000,
        changed_paths=tuple(f"src/file-{index}.ts" for index in range(150)),
        verification_commands=("pnpm test",),
        objective="Repair the implementation",
    )
    path = persist_escalation_package(tmp_path, package)
    assert path.is_file()
    assert len(package.diagnostic) == 6000
    assert len(package.changed_paths) == 100

    selected = recommend_escalation(
        tmp_path,
        req,
        failed_tier="local",
        availability=availability(local=False, free=False, codex=True, claude=True),
        work="issue-x",
    )
    assert selected is not None
    assert selected.tier == "paid-efficient"


def test_repair_advice_is_non_authoritative_bounded_handback():
    advice = build_repair_advice(
        work="issue-x",
        escalation_digest="sha256:abc",
        planner_tier="paid-efficient",
        planner_agent="codex",
        summary="The failing test indicates an incorrect boundary.",
        actions=("Change the boundary condition.", "Run the focused test."),
    )
    handback = render_executor_handback(advice)
    assert "non-authoritative planner" in handback
    assert "Do not infer approval" in handback
    assert "Change the boundary condition." in handback


def test_economic_summary_separates_selection_tiers(tmp_path):
    record_economic_event(
        tmp_path,
        work="issue-x",
        kind="runtime-selected",
        tier="local",
        agent="opencode",
        model="qwen",
    )
    record_economic_event(
        tmp_path,
        work="issue-x",
        kind="escalation-recommended",
        tier="paid-efficient",
        agent="codex",
        model="small",
    )
    summary = summarize_economics(tmp_path, "issue-x")
    assert summary["events"] == 2
    assert summary["runtime_selections_by_tier"] == {"local": 1}
    assert summary["paid_events"] == 0


def test_planner_escalation_respects_core_budget(tmp_path):
    project(tmp_path, paid=True)
    config_path = tmp_path / "ai-sdlc" / "project.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    for candidate in payload["routing"]["candidates"]:
        if candidate["tier"] == "paid-efficient":
            candidate["projected_usage"] = {"tokens": 100}
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    req = requirements_for_activity("construction.implementation", tier="standard")
    budget = Budget(
        scope="work:delivery/issue-x",
        limits={"tokens": 1000},
        consumed={"tokens": 950},
        measurement={"tokens": "provider-reported"},
    )
    with pytest.raises(RuntimePoolError, match="routing.blocked"):
        recommend_escalation(
            tmp_path,
            req,
            failed_tier="local",
            availability=availability(local=False, free=False, codex=True, claude=True),
            work="issue-x",
            budgets=(budget,),
        )


def test_advisory_planner_is_read_only_and_persists_bounded_advice(tmp_path, monkeypatch):
    monkeypatch.setattr("agora_ai_sdlc.advisory_planner.shutil.which", lambda name: f"/bin/{name}")
    req = requirements_for_activity("construction.implementation", tier="standard")
    binding = RuntimeBinding(
        AgentRuntimeRef("codex", "codex"),
        ModelRuntimeRef("openai", "openai", "configured-efficient"),
    )
    package = build_escalation_package(
        swarm="delivery",
        work="issue-x",
        requirements=req,
        failed_tier="local",
        failed_binding=binding,
        attempts=3,
        diagnostic="Focused failing assertion",
        objective="Repair one boundary condition",
    )
    seen = {}

    def runner(argv, stdin, root):
        seen["argv"] = argv
        seen["stdin"] = stdin
        seen["root"] = root
        return 0, '{"summary":"Boundary is inverted","actions":["Invert the condition","Run the focused test"]}'

    outcome = run_advisory_planner(
        tmp_path,
        package=package,
        binding=binding,
        tier="paid-efficient",
        runner=runner,
    )

    assert "--sandbox" in seen["argv"]
    sandbox_index = seen["argv"].index("--sandbox")
    assert seen["argv"][sandbox_index + 1] == "read-only"
    assert "READ-ONLY" in seen["stdin"]
    assert "Do not edit files" in seen["stdin"]
    assert outcome.advice.planner_agent == "codex"
    assert outcome.advice.actions == ("Invert the condition", "Run the focused test")
    assert (tmp_path / ".agora" / "ai-sdlc" / "repair-advice" / "issue-x" / "ADVICE.json").is_file()


def test_paid_telemetry_counts_actual_activity_not_recommendations(tmp_path):
    record_economic_event(
        tmp_path,
        work="issue-x",
        kind="escalation-recommended",
        tier="paid-efficient",
        agent="codex",
        model="small",
    )
    record_economic_event(
        tmp_path,
        work="issue-x",
        kind="runtime-selected",
        tier="paid-efficient",
        agent="codex",
        model="small",
    )
    summary = summarize_economics(tmp_path, "issue-x")
    assert summary["paid_events"] == 1
    assert summary["runtime_selections_by_tier"] == {"paid-efficient": 1}
