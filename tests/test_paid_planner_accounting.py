from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agora_ai_sdlc.advisory_planner import PlannerOutcome, run_advisory_planner
from agora_ai_sdlc.escalation import EscalationPackage, run_escalation_advisor
from agora_ai_sdlc.execution_economics import EconomicsEvent, record_event, summarize_economics
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.repair_advice import build_repair_advice, persist_repair_advice
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding
from agora_ai_sdlc.runtime_pool import RuntimePoolError, select_from_runtime_pool


def discovery(runtime_id: str, *, ok: bool = True):
    return RuntimeDiscovery(
        runtime_id,
        runtime_id,
        runtime_id,
        ok,
        f"/bin/{runtime_id}" if ok else None,
        ok,
        "1.0",
        True,
    )


def write_routing(root: Path):
    path = root / "ai-sdlc" / "project.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "routing": {
                    "profile": "cheap-first",
                    "allow_paid_auto": True,
                    "allow_frontier_auto": False,
                    "retry_limits": {"local": 2, "free": 1},
                    "call_budgets": {"paid-efficient": 4},
                    "candidates": [
                        {
                            "tier": "paid-efficient",
                            "agent": "codex",
                            "model": "openai/configured-efficient",
                            "purposes": ["planner"],
                        },
                        {
                            "tier": "paid-standard",
                            "agent": "claude",
                            "model": "anthropic/configured-standard",
                            "purposes": ["planner"],
                        },
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def package():
    return EscalationPackage(
        swarm="delivery",
        work="issue-x",
        stage="construction",
        objective="Repair the bounded failure",
        acceptance_criteria=("tests pass",),
        failed_agent="opencode",
        failed_model="ollama/qwen3-coder:latest",
        failed_tier="local",
        attempts=3,
        error="focused assertion failed",
        verification_diagnostic="pytest: one assertion failed",
        changed_paths=("src/a.py",),
        dirty_paths=("src/a.py",),
        verification_commands=("pytest -q",),
        risks=(),
    )


def test_advisory_codex_is_read_only_and_captures_reported_usage(tmp_path, monkeypatch):
    monkeypatch.setattr("agora_ai_sdlc.advisory_planner.shutil.which", lambda name: f"/bin/{name}")
    binding = RuntimeBinding(
        AgentRuntimeRef("codex", "codex"),
        ModelRuntimeRef("openai", "openai", "configured-efficient"),
    )
    seen = {}

    def runner(argv, stdin, root):
        seen["argv"] = argv
        seen["stdin"] = stdin
        return 0, '{"summary":"Invert the boundary","actions":["Change the condition"]}\ntokens used\n1,234\n'

    outcome = run_advisory_planner(
        tmp_path,
        package=package(),
        binding=binding,
        tier="paid-efficient",
        runner=runner,
    )

    assert "--sandbox" in seen["argv"]
    assert seen["argv"][seen["argv"].index("--sandbox") + 1] == "read-only"
    assert "READ-ONLY" in seen["stdin"]
    assert outcome.usage == {"tokens": 1234}
    assert outcome.advice.actions == ("Change the condition",)


def test_unaccounted_paid_usage_blocks_later_paid_planner(tmp_path):
    write_routing(tmp_path)
    record_event(
        tmp_path,
        EconomicsEvent(
            "planner-usage-unaccounted",
            "issue-x",
            "paid-efficient",
            "codex",
            "configured-efficient",
            purpose="diagnostic-advisor",
            reason="provider-telemetry-unavailable",
        ),
    )

    requirements = requirements_for_activity("exploration.read_only", tier="standard")
    with pytest.raises(RuntimePoolError, match="routing.no_candidate"):
        select_from_runtime_pool(
            tmp_path,
            requirements,
            availability={"codex": discovery("codex"), "claude": discovery("claude")},
            work_id="issue-x",
            minimum_tier="paid-efficient",
            maximum_tier="paid-standard",
            allowed_agents=("codex", "claude"),
            purpose="planner",
        )

    assert summarize_economics(tmp_path, "issue-x")["unaccounted_paid_usage"] == 1


class FakeWorkspace:
    def __init__(self):
        self.added = []

    def summarize_usage(self, swarm, work):
        return SimpleNamespace(
            budget_limits=None,
            consumed={},
            consumed_measurement={},
            remaining=None,
        )

    def list_usage(self, swarm, work):
        return []

    def add_usage(self, data):
        self.added.append(data)
        return data


def test_escalation_records_provider_reported_usage_in_core(tmp_path, monkeypatch):
    write_routing(tmp_path)
    advice = build_repair_advice(
        work="issue-x",
        escalation_digest=str(package().to_dict()["digest"]),
        planner_tier="paid-efficient",
        planner_agent="codex",
        summary="Focused diagnosis",
        actions=("Apply bounded change",),
    )
    advice_path = persist_repair_advice(tmp_path, advice)

    def fake_planner(root, *, package, binding, tier):
        return PlannerOutcome(
            advice=advice,
            path=str(advice_path),
            raw_output="ok",
            usage={"tokens": 321},
        )

    monkeypatch.setattr("agora_ai_sdlc.advisory_planner.run_advisory_planner", fake_planner)
    workspace = FakeWorkspace()

    result = run_escalation_advisor(
        tmp_path,
        package(),
        availability={"codex": discovery("codex"), "claude": discovery("claude")},
        workspace=workspace,
        actor_id="project:developer",
    )

    assert result.tier == "paid-efficient"
    assert len(workspace.added) == 1
    usage = workspace.added[0]
    assert usage.amounts == {"tokens": 321}
    if "measurement" in getattr(type(usage), "__dataclass_fields__", {}):
        assert usage.measurement == "provider-reported"
    assert usage.actor_id == "project:developer"
    summary = summarize_economics(tmp_path, "issue-x")
    assert summary["unaccounted_paid_usage"] == 0
