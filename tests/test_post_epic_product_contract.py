from pathlib import Path
from types import SimpleNamespace

import tomllib
import yaml

from agora_ai_sdlc.context_manifest import build_context_manifest
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_context import ExecutionContextSelection
from agora_ai_sdlc.execution_economics import record_context_event, render_economics
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.executor_launch import ExecutorLaunchError
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.guided_execution import execute_guided_preparation
from agora_ai_sdlc.progress_events import ProgressEmitter, render_chat, render_jsonl, render_tty
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_pool import select_from_runtime_pool


def test_post_epic_product_contract_is_one_flow_surface_with_bounded_observable_execution(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]

    # One package contract: Flow installs its deterministic kernel and local
    # decision plane; users do not assemble three products.
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]
    scripts = project["project"]["scripts"]
    assert scripts["aisdlc"] == "agora_ai_sdlc.cli:main"
    assert any(item.startswith("agora-framework") for item in dependencies)
    assert any(item.startswith("laya") for item in dependencies)

    # Normal public surfaces must not leak low-level Core CLI operation.
    public = "\n".join(
        (root / path).read_text(encoding="utf-8").casefold()
        for path in (
            "README.md",
            "skills/agora-ai-sdlc-guided/SKILL.md",
            "skills/agora-ai-sdlc-guided/references/construction.md",
        )
    )
    for command in ("agora work ", "agora approval ", "agora artifact ", "agora evidence ", "agora session "):
        assert command not in public

    # The same semantic fact can be projected to terminal/chat/machine without
    # asking a generative model to narrate orchestration.
    event = ProgressEmitter(swarm="delivery", work="issue-319").event(
        "routing",
        "completed",
        "runtime-selection",
        "routing.local_selected",
        facts={"summary": "Local/free executor selected", "tier": "local"},
    )
    assert "Local/free executor selected" in render_tty(event)
    assert "Local/free executor selected" in render_chat(event)
    assert '"tier":"local"' in render_jsonl(event)

    # Mandatory governance remains in the bounded manifest independently of
    # optional repository pruning.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    bundle = ExecutionBundle(
        schema="s",
        swarm="delivery",
        work="issue-319",
        stage="construction",
        next_action="implement",
        branch="feature/319",
        base_branch="main",
        head="abc",
        objective="post-epic acceptance",
        acceptance_criteria=("works",),
        changed_paths=("src/feature.py",),
        dirty_paths=(),
        related_paths=("src/feature.py",),
        languages=("python",),
        build_systems=("pytest",),
        verification_commands=("pytest",),
        risks=(),
        governance={"human_approval_required": False},
        deterministic_inception_path=None,
    )
    selection = ExecutionContextSelection(
        candidate_paths=("src/feature.py",),
        selected_paths=("src/feature.py",),
        protected_paths=("src/feature.py",),
        escalated_paths=(),
        classifications={"src/feature.py": "required"},
        confidences={"src/feature.py": 1.0},
        candidate_tokens=100,
        selected_tokens=50,
        latency_ms=0.0,
    )
    manifest = build_context_manifest(tmp_path, bundle, selection)
    mandatory = {item.id for item in manifest.mandatory}
    assert {"work-identity", "acceptance-criteria", "governance", "risk-policy", "verification"} <= mandatory

    # Economics distinguishes an estimate from observed provider usage and does
    # not manufacture counterfactual savings.
    record_context_event(
        tmp_path,
        work="issue-319",
        before=100,
        after=50,
        basis="estimated_tokens",
    )
    economics = render_economics(tmp_path, "issue-319")
    assert "basis=estimated_tokens; source=estimated" in economics
    assert "No counterfactual token or monetary savings are claimed" in economics

    # Demo products are not architectural dependencies of this acceptance path.
    assert "agorix" not in public



def _available_runtimes():
    return {
        "opencode": RuntimeDiscovery(
            id="opencode",
            name="OpenCode",
            command="opencode",
            installed=True,
            executable="/bin/opencode",
            responsive=True,
            version="test",
            configured=True,
        ),
        "codex": RuntimeDiscovery(
            id="codex",
            name="Codex",
            command="codex",
            installed=True,
            executable="/bin/codex",
            responsive=True,
            version="test",
            configured=True,
        ),
    }


def test_post_epic_routing_rejects_cheaper_runtime_when_context_does_not_fit(tmp_path: Path):
    config = tmp_path / "ai-sdlc" / "project.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "routing": {
                    "profile": "cheap-first",
                    "allow_paid_auto": True,
                    "candidates": [
                        {
                            "tier": "local",
                            "agent": "opencode",
                            "model": "ollama/qwen3-coder:latest",
                            "context_limit_tokens": 4096,
                            "cost_class": "free",
                            "locality": "local",
                        },
                        {
                            "tier": "paid-efficient",
                            "agent": "codex",
                            "model": "openai/configured-default",
                            "context_limit_tokens": 32768,
                            "cost_class": "low",
                            "locality": "remote",
                        },
                    ],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    selected = select_from_runtime_pool(
        tmp_path,
        requirements_for_activity("construction.implementation", tier="standard"),
        availability=_available_runtimes(),
        context_tokens_estimate=12000,
    )

    assert selected is not None
    assert selected.tier == "paid-efficient"
    assert selected.decision["considered"][0]["blockers"] == ("runtime.context_limit_exceeded",)
    assert "cheapest-admissible-tier" in selected.decision["selection_reasons"]


def test_post_epic_human_boundary_stops_before_executor(monkeypatch, tmp_path: Path):
    events = []
    decision = GuidedDecision(
        swarm="delivery",
        work="issue-319",
        title="Approve release",
        method="ai-sdlc",
        actor="project:product-owner",
        role="product-owner",
        state="inception",
        target="construction",
        gate="inception-approved",
        blockers=("approval required",),
        messages=("Human approval required.",),
        missing_approvals=("product-owner",),
        ready_for_human_approval=True,
    )
    runtime = SimpleNamespace(
        id="codex",
        name="Codex",
        installed=True,
        responsive=True,
        executable="/bin/codex",
        command="codex",
        version="test",
    )
    monkeypatch.setattr("agora_ai_sdlc.guided_execution._runtime", lambda *args, **kwargs: runtime)

    try:
        execute_guided_preparation(
            tmp_path,
            decision,
            runtime_id="codex",
            progress_event=events.append,
        )
    except ExecutorLaunchError as error:
        assert "human-boundary" in str(error)
    else:
        raise AssertionError("human approval boundary must stop AI execution")

    assert len(events) == 1
    assert events[0].kind == "human-boundary"
    assert events[0].status == "blocked"
