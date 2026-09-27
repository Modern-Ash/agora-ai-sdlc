from pathlib import Path
from types import SimpleNamespace

import yaml

from agora_ai_sdlc.escalation import EscalationPackage, run_escalation_advisor
from agora_ai_sdlc.execution_economics import EconomicsEvent, attempt_count, record_event, summarize_economics
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_pool import retry_limit_for, select_from_runtime_pool


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
    adapter = FakeAdapter()
    monkeypatch.setattr("agora_ai_sdlc.escalation.default_registry", lambda root: FakeRegistry(adapter))
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

    result = run_escalation_advisor(tmp_path, package, availability=availability())

    assert result.binding.agent.id == "codex"
    assert result.tier == "paid-efficient"
    assert "parser branch" in result.advice
    assert Path(result.package_path).is_file()
    assert Path(result.advice_path).is_file()
    assert adapter.payload["next_transition"]["operation"] == "diagnostic.advise"
    events = summarize_economics(tmp_path, "w")
    assert events["attempts"]["paid-efficient"] == 1
    assert events["escalations"] == 1
