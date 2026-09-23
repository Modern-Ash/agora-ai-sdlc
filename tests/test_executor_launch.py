from pathlib import Path
from types import SimpleNamespace

import pytest
from agora.markdown import MarkdownDocument, render_markdown

from agora_ai_sdlc.executor_launch import (
    ExecutorLaunchError,
    build_executor_runner,
    executor_capable,
    launch_inception_executor,
)
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery


def runtime(runtime_id: str = "opencode") -> RuntimeDiscovery:
    return RuntimeDiscovery(
        id=runtime_id,
        name={"opencode": "OpenCode", "codex": "Codex", "claude": "Claude Code", "ollama": "Ollama"}[runtime_id],
        command=runtime_id,
        installed=True,
        executable=f"/usr/bin/{runtime_id}",
        responsive=True,
        version="1.0",
        configured=True,
    )


def write_result(session_path: Path, output: str) -> None:
    session_path.mkdir(parents=True, exist_ok=True)
    result = render_markdown(
        MarkdownDocument(
            attributes={
                "schema": "agora/session-result/v1",
                "session": session_path.name,
                "status": "completed",
                "exit-code": 0,
            },
            body=(
                f"# Session result {session_path.name}\n\n"
                f"## Standard output\n\n"
                + "\n".join(f"    {line}" for line in output.splitlines())
                + "\n\n## Standard error\n\n    (empty)"
            ),
        )
    )
    (session_path / "RESULT.md").write_text(result, encoding="utf-8")
    (session_path / "SUMMARY.md").write_text("# summary\n", encoding="utf-8")


class Workspace:
    def __init__(self, cwd: Path, sessions=None):
        self.cwd = cwd
        self.sessions = list(sessions or [])
        self.started = []
        self.launched = []

    def list_sessions(self):
        return list(self.sessions)

    def start_session(self, data):
        self.started.append(data)
        path = self.cwd / ".agora" / "sessions" / data.id
        write_result(path, "## Inception Proposal\n\nPlan ready.\n\n## Human decision required\n\nApprove or modify.")
        record = SimpleNamespace(
            id=data.id,
            status="completed",
            path=str(path),
            retry_of=getattr(data, "retry_of", None),
            exit_code=0,
            created_at="2026-09-23T00:00:00Z",
        )
        self.sessions.append(record)
        return record

    def launch_session(self, data):
        self.launched.append(data)
        existing = next(item for item in self.sessions if item.id == data.session_id)
        path = Path(existing.path)
        write_result(path, "Prepared session completed.")
        existing.status = "completed"
        existing.exit_code = 0
        return existing


def handoff(root: Path) -> Path:
    path = root / ".agora" / "ai-sdlc" / "handoffs" / "issue-14" / "INCEPTION_HANDOFF.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# handoff\n", encoding="utf-8")
    return path


def test_executor_registry_distinguishes_agent_host_from_model_provider():
    assert executor_capable("opencode") is True
    assert executor_capable("codex") is True
    assert executor_capable("claude") is True
    assert executor_capable("ollama") is False


def test_opencode_runner_is_non_interactive_and_binds_handoff_and_root(tmp_path):
    runner = build_executor_runner(runtime("opencode"), tmp_path, handoff(tmp_path))

    assert runner.startswith("/usr/bin/opencode run ")
    assert "INCEPTION_HANDOFF.md" in runner
    assert str(tmp_path.resolve()) in runner
    assert "Do not implement product code" in runner


def test_provider_only_runtime_fails_with_actionable_guidance(tmp_path):
    with pytest.raises(ExecutorLaunchError, match="not a repository executor"):
        build_executor_runner(runtime("ollama"), tmp_path, handoff(tmp_path))


def test_launch_uses_governed_core_session_in_exact_workspace(tmp_path):
    workspace = Workspace(tmp_path)

    result = launch_inception_executor(
        tmp_path,
        runtime=runtime("opencode"),
        handoff_path=handoff(tmp_path),
        swarm_id="delivery",
        work_id="issue-14",
        workspace_factory=lambda cwd: workspace,
    )

    assert workspace.cwd == tmp_path
    assert len(workspace.started) == 1
    started = workspace.started[0]
    assert started.actor_id == "product-owner"
    assert started.swarm_id == "delivery"
    assert started.work_id == "issue-14"
    assert started.executor_id == "ai-opencode"
    assert started.launch is True
    assert started.runner.startswith("/usr/bin/opencode run ")
    assert result.status == "completed"
    assert result.reused is False
    assert "Plan ready." in result.output


def test_completed_inception_session_is_reused_without_relaunch(tmp_path):
    path = tmp_path / ".agora" / "sessions" / "ai-sdlc-inception-issue-14"
    write_result(path, "Existing proposal.")
    completed = SimpleNamespace(
        id="ai-sdlc-inception-issue-14",
        status="completed",
        path=str(path),
        retry_of=None,
        exit_code=0,
        created_at="2026-09-23T00:00:00Z",
    )
    workspace = Workspace(tmp_path, [completed])

    result = launch_inception_executor(
        tmp_path,
        runtime=runtime("opencode"),
        handoff_path=handoff(tmp_path),
        swarm_id="delivery",
        work_id="issue-14",
        workspace_factory=lambda cwd: workspace,
    )

    assert workspace.started == []
    assert result.reused is True
    assert result.output == "Existing proposal."


def test_failed_inception_gets_a_new_governed_retry_session(tmp_path):
    failed_path = tmp_path / ".agora" / "sessions" / "ai-sdlc-inception-issue-14"
    failed_path.mkdir(parents=True)
    (failed_path / "SUMMARY.md").write_text("# failed\n", encoding="utf-8")
    failed = SimpleNamespace(
        id="ai-sdlc-inception-issue-14",
        status="failed",
        path=str(failed_path),
        retry_of=None,
        exit_code=1,
        created_at="2026-09-23T00:00:00Z",
    )
    workspace = Workspace(tmp_path, [failed])

    result = launch_inception_executor(
        tmp_path,
        runtime=runtime("opencode"),
        handoff_path=handoff(tmp_path),
        swarm_id="delivery",
        work_id="issue-14",
        workspace_factory=lambda cwd: workspace,
    )

    assert workspace.started[0].id == "ai-sdlc-inception-issue-14-retry-2"
    assert workspace.started[0].retry_of == "ai-sdlc-inception-issue-14"
    assert result.retry_of == "ai-sdlc-inception-issue-14"


def test_completed_session_without_output_does_not_create_false_human_review(tmp_path):
    path = tmp_path / ".agora" / "sessions" / "ai-sdlc-inception-issue-14"
    write_result(path, "")
    completed = SimpleNamespace(
        id="ai-sdlc-inception-issue-14",
        status="completed",
        path=str(path),
        retry_of=None,
        exit_code=0,
        created_at="2026-09-23T00:00:00Z",
    )
    workspace = Workspace(tmp_path, [completed])

    with pytest.raises(ExecutorLaunchError, match="without reviewable output"):
        launch_inception_executor(
            tmp_path,
            runtime=runtime("opencode"),
            handoff_path=handoff(tmp_path),
            swarm_id="delivery",
            work_id="issue-14",
            workspace_factory=lambda cwd: workspace,
        )
