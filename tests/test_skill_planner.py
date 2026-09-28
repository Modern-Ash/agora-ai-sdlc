from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import yaml

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_economics import summarize_economics
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.skill_planner import maybe_plan_skill


def runtime(runtime_id: str, ok: bool = True):
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


def bundle(stage="inception"):
    return ExecutionBundle(
        schema="s",
        swarm="delivery",
        work="issue-plan",
        stage=stage,
        next_action="inspect-next",
        branch=None,
        base_branch=None,
        head=None,
        objective="Implement bounded feature",
        acceptance_criteria=("feature works",),
        changed_paths=("src/a.py",),
        dirty_paths=(),
        related_paths=("tests/test_a.py",),
        languages=("python",),
        build_systems=("pytest",),
        verification_commands=("pytest -q",),
        risks=(),
        governance={},
        deterministic_inception_path=None,
    )


def config(root: Path, *, paid=True):
    path = root / "ai-sdlc" / "project.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "routing": {
                    "profile": "cheap-first",
                    "allow_paid_auto": paid,
                    "allow_frontier_auto": False,
                    "candidates": [
                        {
                            "tier": "local",
                            "agent": "opencode",
                            "model": "ollama/qwen3-coder:latest",
                        },
                        {
                            "tier": "paid-efficient",
                            "agent": "codex",
                            "model": "openai/gpt-efficient",
                        },
                        {
                            "tier": "paid-standard",
                            "agent": "claude",
                            "model": "anthropic/claude-standard",
                        },
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    skill = root / ".agora" / "skills" / "agora-ai-sdlc-guided"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Guided skill\nPlan before executing.\n", encoding="utf-8")
    (skill / "references" / "inception.md").write_text("# Inception\nKeep scope bounded.\n", encoding="utf-8")


def availability():
    return {
        "codex": runtime("codex"),
        "claude": runtime("claude"),
        "opencode": runtime("opencode"),
    }


class FakeAdapter:
    def __init__(self):
        self.launches = 0
        self.payload = None

    def prepare_execution(self, payload):
        self.payload = payload
        capabilities = set(payload["requirements"]["required_capabilities"])
        assert "workspace.read" in capabilities
        assert "workspace.write" not in capabilities
        return SimpleNamespace(argv=("fake",), stdin="", model="gpt-efficient")

    def launch(self, prepared, runner):
        self.launches += 1
        return SimpleNamespace(
            exit_code=0,
            output="1. Read src/a.py.\n2. Change only the bounded feature.\n3. Run pytest -q.",
        )


class FakeRegistry:
    def __init__(self, adapter):
        self.adapter = adapter

    def get(self, agent):
        return self.adapter


def planner_requirements(mode: str):
    return replace(
        requirements_for_activity("inception.elaboration", tier="standard"),
        planner_needed=mode,
    )


def test_inception_skips_planner_when_laya_says_none(tmp_path, monkeypatch):
    config(tmp_path)
    adapter = FakeAdapter()
    monkeypatch.setattr("agora_ai_sdlc.skill_planner.default_registry", lambda root: FakeRegistry(adapter))
    monkeypatch.setattr(
        "agora_ai_sdlc.skill_planner.requirements_for",
        lambda *args, **kwargs: planner_requirements("none"),
    )

    result = maybe_plan_skill(tmp_path, bundle(), availability=availability())

    assert result is None
    assert adapter.launches == 0
    assert summarize_economics(tmp_path, "issue-plan")["attempts"] == {}


def test_inception_uses_paid_efficient_planner_only_when_requested(tmp_path, monkeypatch):
    config(tmp_path)
    adapter = FakeAdapter()
    monkeypatch.setattr("agora_ai_sdlc.skill_planner.default_registry", lambda root: FakeRegistry(adapter))
    monkeypatch.setattr(
        "agora_ai_sdlc.skill_planner.requirements_for",
        lambda *args, **kwargs: planner_requirements("generative"),
    )

    result = maybe_plan_skill(tmp_path, bundle(), availability=availability())

    assert result is not None
    assert result.binding.agent.id == "codex"
    assert result.tier == "paid-efficient"
    assert not result.reused
    assert Path(result.path).is_file()
    assert "Run pytest -q" in result.text
    assert adapter.payload["next_transition"]["operation"] == "planning.advise"
    assert adapter.payload["context"]["purpose"] == "skill-planner"

    economics = summarize_economics(tmp_path, "issue-plan")
    assert economics["attempts"] == {"paid-efficient": 1}
    assert economics["successes"] == {"paid-efficient": 1}


def test_same_skill_and_bundle_reuses_paid_plan_without_second_call(tmp_path, monkeypatch):
    config(tmp_path)
    adapter = FakeAdapter()
    monkeypatch.setattr("agora_ai_sdlc.skill_planner.default_registry", lambda root: FakeRegistry(adapter))
    monkeypatch.setattr(
        "agora_ai_sdlc.skill_planner.requirements_for",
        lambda *args, **kwargs: planner_requirements("generative"),
    )

    first = maybe_plan_skill(tmp_path, bundle(), availability=availability())
    second = maybe_plan_skill(tmp_path, bundle(), availability=availability())

    assert first is not None and second is not None
    assert first.input_digest == second.input_digest
    assert second.reused
    assert adapter.launches == 1


def test_planner_skips_when_paid_auto_is_not_authorized(tmp_path, monkeypatch):
    config(tmp_path, paid=False)
    adapter = FakeAdapter()
    monkeypatch.setattr("agora_ai_sdlc.skill_planner.default_registry", lambda root: FakeRegistry(adapter))
    monkeypatch.setattr(
        "agora_ai_sdlc.skill_planner.requirements_for",
        lambda *args, **kwargs: planner_requirements("generative"),
    )

    result = maybe_plan_skill(tmp_path, bundle(), availability=availability())

    assert result is None
    assert adapter.launches == 0


def test_local_construction_does_not_pay_for_planning(tmp_path, monkeypatch):
    config(tmp_path)
    adapter = FakeAdapter()
    monkeypatch.setattr("agora_ai_sdlc.skill_planner.default_registry", lambda root: FakeRegistry(adapter))

    result = maybe_plan_skill(tmp_path, bundle("construction"), availability=availability())

    assert result is None
    assert adapter.launches == 0


def test_partial_legacy_bundle_fails_open_without_planner_call(tmp_path, monkeypatch):
    config(tmp_path)
    adapter = FakeAdapter()
    monkeypatch.setattr("agora_ai_sdlc.skill_planner.default_registry", lambda root: FakeRegistry(adapter))
    partial = SimpleNamespace(
        swarm="delivery",
        work="legacy-work",
        stage="inception",
        markdown_path=str(tmp_path / "EXECUTION_BUNDLE.md"),
    )

    result = maybe_plan_skill(tmp_path, partial, availability=availability())

    assert result is None
    assert adapter.launches == 0
