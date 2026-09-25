from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc import construction_executor
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery


def runtime():
    return RuntimeDiscovery(
        id="claude",
        name="Claude Code",
        command="claude",
        installed=True,
        executable="/bin/claude",
        responsive=True,
        version="1.0",
        configured=True,
    )


class Workspace:
    def __init__(self, cwd):
        self.cwd = Path(cwd)
        self.started = []

    def start_session(self, data):
        self.started.append(data)
        session = self.cwd / ".agora" / "sessions" / data.id
        session.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(
            id=data.id,
            status="completed",
            path=str(session),
            exit_code=0,
        )


def test_launch_construction_executor_uses_deterministic_bundle_and_assigned_actor(monkeypatch, tmp_path):
    bundle_path = tmp_path / ".agora" / "ai-sdlc" / "bundles" / "issue-26" / "EXECUTION_BUNDLE.json"
    bundle_path.parent.mkdir(parents=True)
    bundle_path.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        construction_executor,
        "resolve_work_workspace",
        lambda root, work: tmp_path,
    )
    monkeypatch.setattr(
        construction_executor,
        "build_execution_bundle",
        lambda *args, **kwargs: SimpleNamespace(
            stage="construction",
            json_path=str(bundle_path),
        ),
    )
    monkeypatch.setattr(
        construction_executor,
        "build_runtime_runner",
        lambda runtime, root, prompt, model=None: "claude --print construction",
    )
    monkeypatch.setattr(
        construction_executor,
        "_matching_sessions",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        construction_executor,
        "_session_output",
        lambda path: "Implemented issue #26",
    )

    workspace = Workspace(tmp_path)
    result = construction_executor.launch_construction_executor(
        tmp_path,
        swarm_id="issue-26-demo",
        work_id="issue-26",
        actor_reference="project:ai-claude",
        runtime=runtime(),
        workspace_factory=lambda cwd: workspace,
    )

    assert result.status == "completed"
    assert result.output == "Implemented issue #26"
    assert len(workspace.started) == 1
    data = workspace.started[0]
    assert data.actor_id == "project:ai-claude"
    assert data.swarm_id == "issue-26-demo"
    assert data.work_id == "issue-26"
    assert data.runner == "claude --print construction"


def _patch_common(monkeypatch, tmp_path, sessions):
    bundle_path = tmp_path / "EXECUTION_BUNDLE.json"
    bundle_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(construction_executor, "resolve_work_workspace", lambda root, work: tmp_path)
    monkeypatch.setattr(
        construction_executor,
        "build_execution_bundle",
        lambda *a, **k: SimpleNamespace(stage="construction", json_path=str(bundle_path)),
    )
    monkeypatch.setattr(construction_executor, "build_runtime_runner", lambda *a, **k: "runner")
    monkeypatch.setattr(construction_executor, "_matching_sessions", lambda *a, **k: sessions)
    monkeypatch.setattr(construction_executor, "_session_output", lambda path: "")


def test_completed_session_is_not_reused_and_noop_run_fails_closed(monkeypatch, tmp_path):
    stale = SimpleNamespace(id="ai-sdlc-construction-issue-26", status="completed", path=str(tmp_path))
    _patch_common(monkeypatch, tmp_path, [stale])
    monkeypatch.setattr(
        construction_executor,
        "reconcile_construction_execution",
        lambda *a, **k: SimpleNamespace(registered_artifacts=(), criterion_stages=(), verification_passed=False),
    )
    workspace = Workspace(tmp_path)
    try:
        construction_executor.launch_construction_executor(
            tmp_path,
            swarm_id="s",
            work_id="issue-26",
            actor_reference="project:a",
            runtime=runtime(),
            workspace_factory=lambda cwd: workspace,
            decision=SimpleNamespace(state="construction"),
        )
    except construction_executor.ExecutorLaunchError as error:
        assert "no observable" in str(error)
    else:
        raise AssertionError("no-op run must fail closed")
    assert workspace.started[0].id.endswith("-rerun-2")
