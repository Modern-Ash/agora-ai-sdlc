from pathlib import Path
from types import SimpleNamespace

import yaml

from agora_ai_sdlc.advisory_planner import PlannerOutcome
from agora_ai_sdlc.escalation import EscalationPackage, run_escalation_advisor
from agora_ai_sdlc.execution_economics import (
    EconomicsEvent,
    attempt_count,
    load_events,
    record_context_event,
    record_decision_event,
    record_event,
    record_executor_event,
    render_economics,
    summarize_economics,
)
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.repair_advice import build_repair_advice, persist_repair_advice
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_pool import (
    configured_context_limit,
    retry_limit_for,
    select_from_runtime_pool,
)


def discovery(runtime_id, *, ok=True, models=()):
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


def write_config(root: Path, *, call_budgets=None, retry_limits=None):
    path = root / "ai-sdlc" / "project.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "routing": {
                    "profile": "cheap-first",
                    "allow_paid_auto": True,
                    "allow_frontier_auto": False,
                    "call_budgets": call_budgets or {},
                    "retry_limits": retry_limits or {"local": 2, "free": 1},
                    "candidates": [
                        {"tier": "local", "agent": "opencode", "model": "ollama/qwen3-coder:latest"},
                        {"tier": "paid-efficient", "agent": "codex", "model": "openai/gpt-efficient"},
                        {"tier": "paid-standard", "agent": "claude", "model": "anthropic/claude-standard"},
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def availability():
    return {
        "opencode": discovery("opencode"),
        "ollama": discovery("ollama", models=("qwen3-coder:latest",)),
        "codex": discovery("codex"),
        "claude": discovery("claude"),
    }


def test_economics_ledger_counts_attempts_and_escalations(tmp_path):
    record_event(tmp_path, EconomicsEvent("attempt", "w", "local", "opencode", "qwen"))
    record_event(tmp_path, EconomicsEvent("failure", "w", "local", "opencode", "qwen"))
    record_event(tmp_path, EconomicsEvent("attempt", "w", "paid-efficient", "codex", "small"))
    record_event(tmp_path, EconomicsEvent("success", "w", "paid-efficient", "codex", "small"))
    record_event(tmp_path, EconomicsEvent("escalation", "w", "paid-efficient", "codex", "small"))

    summary = summarize_economics(tmp_path, "w")

    assert attempt_count(tmp_path, "w", "local") == 1
    assert summary["attempts"] == {"local": 1, "paid-efficient": 1}
    assert summary["failures"] == {"local": 1}
    assert summary["successes"] == {"paid-efficient": 1}
    assert summary["escalations"] == 1


def test_executor_event_uses_selected_binding_and_tier(tmp_path):
    plan = SimpleNamespace(
        execution_tier="local",
        binding=SimpleNamespace(
            agent=SimpleNamespace(id="opencode"),
            model=SimpleNamespace(model="qwen3-coder:latest"),
        ),
    )
    runtime = SimpleNamespace(id="opencode")

    record_executor_event(
        tmp_path,
        event="attempt",
        work="w",
        swarm="delivery",
        runtime=runtime,
        plan=plan,
        reason="construction",
    )

    event = load_events(tmp_path, "w")[0]
    assert event["tier"] == "local"
    assert event["agent"] == "opencode"
    assert event["model"] == "qwen3-coder:latest"
    assert event["purpose"] == "executor"
    route = summarize_economics(tmp_path, "w")["routes"][0]
    assert route == {
        "tier": "local",
        "purpose": "executor",
        "agent": "opencode",
        "model": "qwen3-coder:latest",
        "attempts": 1,
        "successes": 0,
        "failures": 0,
    }


def test_tier_call_budget_forces_next_cheapest_candidate(tmp_path):
    write_config(tmp_path, call_budgets={"local": 1})
    record_event(tmp_path, EconomicsEvent("attempt", "w", "local", "opencode", "qwen"))
    requirements = requirements_for_activity("construction.implementation", tier="standard")

    selected = select_from_runtime_pool(
        tmp_path,
        requirements,
        availability=availability(),
        work_id="w",
    )

    assert selected is not None
    assert selected.tier == "paid-efficient"
    assert selected.binding.agent.id == "codex"


def test_retry_limits_are_project_configurable(tmp_path):
    write_config(tmp_path, retry_limits={"local": 3, "free": 1})
    assert retry_limit_for(tmp_path, "local") == 3
    assert retry_limit_for(tmp_path, "free") == 1
    assert retry_limit_for(tmp_path, "paid-efficient") == 0


class FakeAdapter:
    def __init__(self):
        self.payload = None

    def prepare_execution(self, payload):
        self.payload = payload
        required = set(payload["requirements"]["required_capabilities"])
        assert "workspace.read" in required
        assert "workspace.write" not in required
        return SimpleNamespace(argv=("fake",), stdin="", model="small")

    def launch(self, prepared, runner):
        return SimpleNamespace(exit_code=0, output="Change the parser branch before retrying.")


class FakeRegistry:
    def __init__(self, adapter):
        self.adapter = adapter

    def get(self, agent):
        return self.adapter


def test_paid_advisor_is_read_only_and_hands_back_advice(tmp_path, monkeypatch):
    write_config(tmp_path)
    package = EscalationPackage(
        swarm="delivery",
        work="w",
        stage="construction",
        objective="repair parser",
        acceptance_criteria=("tests pass",),
        failed_agent="opencode",
        failed_model="ollama/qwen3-coder:latest",
        failed_tier="local",
        attempts=3,
        error="tests failed",
        verification_diagnostic="one assertion failed",
        changed_paths=("src/parser.ts",),
        dirty_paths=("src/parser.ts",),
        verification_commands=("pnpm test",),
        risks=(),
    )
    advice = build_repair_advice(
        work="w",
        escalation_digest=str(package.to_dict()["digest"]),
        planner_tier="paid-efficient",
        planner_agent="codex",
        summary="Parser branch diagnosis",
        actions=("Change the parser branch before retrying.",),
    )
    advice_path = persist_repair_advice(tmp_path, advice)

    monkeypatch.setattr(
        "agora_ai_sdlc.advisory_planner.run_advisory_planner",
        lambda root, *, package, binding, tier: PlannerOutcome(
            advice=advice,
            path=str(advice_path),
            raw_output="ok",
            usage={},
        ),
    )

    result = run_escalation_advisor(tmp_path, package, availability=availability())

    assert result.binding.agent.id == "codex"
    assert result.tier == "paid-efficient"
    assert "parser branch" in result.advice
    assert Path(result.package_path).is_file()
    assert Path(result.advice_path).is_file()
    events = summarize_economics(tmp_path, "w")
    assert events["attempts"]["paid-efficient"] == 1
    assert events["escalations"] == 1



def test_decision_metrics_count_observed_routes_without_claiming_savings(tmp_path):
    record_decision_event(
        tmp_path,
        work="w",
        route="system0",
        reason="explicit-human-boundary",
        generative_call=False,
        tier="deterministic",
    )
    record_decision_event(
        tmp_path,
        work="w",
        route="premium",
        reason="frontier-required",
        generative_call=True,
        tier="premium",
    )

    summary = summarize_economics(tmp_path, "w")

    assert summary["decisions"] == {"premium": 1, "system0": 1}
    assert summary["generative_calls_observed"] == 1
    assert "tokens_saved" not in summary


def test_context_measurement_preserves_estimate_basis(tmp_path):
    record_context_event(
        tmp_path,
        work="w",
        before=48000,
        after=13000,
        basis="estimated_tokens",
    )

    measurement = summarize_economics(tmp_path, "w")["context_measurements"][0]

    assert measurement == {
        "source": "estimated",
        "basis": "estimated_tokens",
        "before": 48000,
        "after": 13000,
        "reduction": 35000,
    }


def test_context_measurement_rejects_unknown_basis(tmp_path):
    try:
        record_context_event(tmp_path, work="w", before=10, after=5, basis="magic-tokens")
    except ValueError as error:
        assert "unsupported context measurement basis" in str(error)
    else:
        raise AssertionError("unknown measurement basis must not be persisted")



def test_render_economics_labels_estimates_and_refuses_counterfactual_claims(tmp_path):
    record_decision_event(
        tmp_path,
        work="w",
        route="laya",
        reason="clarification-no-material-gap",
        generative_call=False,
        tier="system1",
    )
    record_context_event(
        tmp_path,
        work="w",
        before=1000,
        after=400,
        basis="estimated_tokens",
    )

    rendered = render_economics(tmp_path, "w")

    assert "Observed generative calls: 0" in rendered
    assert "laya: 1" in rendered
    assert "basis=estimated_tokens; source=estimated" in rendered
    assert "No counterfactual token or monetary savings are claimed" in rendered



def test_runtime_pool_exposes_only_explicit_context_limit(tmp_path):
    path = tmp_path / "ai-sdlc" / "project.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "routing": {
                    "profile": "cheap-first",
                    "allow_paid_auto": True,
                    "allow_frontier_auto": False,
                    "candidates": [
                        {
                            "tier": "local",
                            "agent": "opencode",
                            "model": "ollama/qwen3-coder:latest",
                            "context_limit_tokens": 32768,
                        }
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    assert configured_context_limit(tmp_path, "opencode", "qwen3-coder:latest") == 32768
    assert configured_context_limit(tmp_path, "codex", None) is None


def test_runtime_pool_rejects_invalid_context_limit(tmp_path):
    path = tmp_path / "ai-sdlc" / "project.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "routing": {
                    "profile": "cheap-first",
                    "candidates": [
                        {
                            "tier": "local",
                            "agent": "opencode",
                            "context_limit_tokens": 0,
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    try:
        configured_context_limit(tmp_path, "opencode")
    except ValueError as error:
        assert "context_limit_tokens" in str(error)
    else:
        raise AssertionError("invalid context limit must fail closed")
