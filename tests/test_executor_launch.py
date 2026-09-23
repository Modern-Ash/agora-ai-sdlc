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


def valid_inception_output(marker: str = "Plan ready.") -> str:
    return (
        "## Intent interpretation\n\n"
        "Implement the deterministic canonical program interpreter described by the governed Intent.\n\n"
        "## Material clarifications\n\n"
        "No unresolved material clarification.\n\n"
        "## Level 1 Plan\n\n"
        f"{marker} Define semantics, deterministic transitions, budget, stop behavior, and tests.\n\n"
        "## Proposed Units\n\n"
        "One cohesive interpreter unit.\n\n"
        "## Suggested Bolts\n\n"
        "One implementation bolt after approval.\n\n"
        "## Acceptance criteria trace\n\n"
        "Trace deterministic interpreter behavior to issue acceptance criteria.\n\n"
        "## Risks, constraints and dependencies\n\n"
        "No eval; depends on the canonical program model.\n\n"
        "## Source facts and proposed decisions\n\n"
        "Source fact: deterministic canonical interpreter. AI proposal: bounded implementation unit.\n\n"
        "## Files created or modified\n\n"
        "No product files modified during Inception.\n\n"
        "## Human decision required\n\n"
        "Approve or modify before Construction.\n"
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
        write_result(path, valid_inception_output())
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
        write_result(path, valid_inception_output("Prepared session completed."))
        existing.status = "completed"
        existing.exit_code = 0
        return existing


def handoff(root: Path) -> Path:
    path = root / ".agora" / "ai-sdlc" / "handoffs" / "issue-14" / "INCEPTION_HANDOFF.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Inception handoff\n\n## Objective\n\nImplement deterministic canonical program interpreter\n",
        encoding="utf-8",
    )
    return path


def test_executor_registry_distinguishes_agent_host_from_model_provider():
    assert executor_capable("opencode") is True
    assert executor_capable("codex") is True
    assert executor_capable("claude") is True
    assert executor_capable("ollama") is False


def test_opencode_runner_is_non_interactive_and_binds_handoff_and_root(tmp_path):
    runner = build_executor_runner(runtime("opencode"), tmp_path, handoff(tmp_path))

    assert "-m agora_ai_sdlc.opencode_runner" in runner
    assert f"--root {tmp_path.resolve()}" in runner
    assert "INCEPTION_HANDOFF.md" in runner
    assert str(tmp_path.resolve()) in runner
    assert "Do not implement product code" in runner


def test_opencode_runner_accepts_explicit_model_override(tmp_path):
    runner = build_executor_runner(
        runtime("opencode"),
        tmp_path,
        handoff(tmp_path),
        model="ollama/claude",
    )

    assert "--model ollama/claude" in runner


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
    assert started.timeout_seconds == 300
    assert "--model" not in started.runner
    assert result.status == "completed"
    assert result.reused is False
    assert "Plan ready." in result.output


def test_unrelated_broken_session_does_not_block_inception_lookup(tmp_path):
    class TargetedWorkspace(Workspace):
        def list_sessions(self):
            raise AssertionError("targeted Core lookup must not scan unrelated sessions")

        def show_session(self, session_id):
            return next(item for item in self.sessions if item.id == session_id)

    unrelated = tmp_path / ".agora" / "sessions" / "unrelated-session" / "SESSION.md"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("# broken session\n", encoding="utf-8")
    workspace = TargetedWorkspace(tmp_path)

    result = launch_inception_executor(
        tmp_path,
        runtime=runtime("opencode"),
        handoff_path=handoff(tmp_path),
        swarm_id="delivery",
        work_id="issue-14",
        workspace_factory=lambda cwd: workspace,
    )

    assert result.status == "completed"
    assert len(workspace.started) == 1


def test_completed_inception_session_is_reused_without_relaunch(tmp_path):
    path = tmp_path / ".agora" / "sessions" / "ai-sdlc-inception-issue-14"
    write_result(path, valid_inception_output("Existing proposal."))
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
    assert "Existing proposal." in result.output


def test_completed_but_invalid_inception_is_not_reused_and_gets_new_attempt(tmp_path):
    invalid_path = tmp_path / ".agora" / "sessions" / "ai-sdlc-inception-issue-14"
    write_result(
        invalid_path,
        "## Inception Proposal\n\nCreate a Flask API client.\n\n## Human decision required\n\nApprove or modify.",
    )
    invalid = SimpleNamespace(
        id="ai-sdlc-inception-issue-14",
        status="completed",
        path=str(invalid_path),
        retry_of=None,
        exit_code=0,
        created_at="2026-09-23T00:00:00Z",
    )
    workspace = Workspace(tmp_path, [invalid])

    result = launch_inception_executor(
        tmp_path,
        runtime=runtime("opencode"),
        handoff_path=handoff(tmp_path),
        swarm_id="delivery",
        work_id="issue-14",
        workspace_factory=lambda cwd: workspace,
    )

    assert workspace.started[0].id == "ai-sdlc-inception-issue-14-retry-2"
    assert getattr(workspace.started[0], "retry_of", None) is None
    assert result.status == "completed"
    assert result.reused is False


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


def test_newly_completed_irrelevant_output_is_recoverable_contract_failure(tmp_path):
    class IrrelevantWorkspace(Workspace):
        def start_session(self, data):
            self.started.append(data)
            path = self.cwd / ".agora" / "sessions" / data.id
            write_result(
                path,
                "## Inception Proposal\n\nCreate a Flask API client.\n\n"
                "## Human decision required\n\nApprove or modify.",
            )
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

    workspace = IrrelevantWorkspace(tmp_path)

    with pytest.raises(ExecutorLaunchError, match="violates the Inception contract") as captured:
        launch_inception_executor(
            tmp_path,
            runtime=runtime("opencode"),
            handoff_path=handoff(tmp_path),
            swarm_id="delivery",
            work_id="issue-14",
            workspace_factory=lambda cwd: workspace,
        )

    assert captured.value.recoverable is True


def test_completed_session_without_output_is_not_reused_and_gets_new_attempt(tmp_path):
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

    result = launch_inception_executor(
        tmp_path,
        runtime=runtime("opencode"),
        handoff_path=handoff(tmp_path),
        swarm_id="delivery",
        work_id="issue-14",
        workspace_factory=lambda cwd: workspace,
    )

    assert workspace.started[0].id == "ai-sdlc-inception-issue-14-retry-2"
    assert result.status == "completed"
    assert result.reused is False


def test_failed_executor_surfaces_provider_stderr(tmp_path):
    class FailingWorkspace(Workspace):
        def start_session(self, data):
            self.started.append(data)
            path = self.cwd / ".agora" / "sessions" / data.id
            path.mkdir(parents=True, exist_ok=True)
            result = render_markdown(
                MarkdownDocument(
                    attributes={
                        "schema": "agora/session-result/v1",
                        "session": data.id,
                        "status": "failed",
                        "exit-code": 70,
                    },
                    body=(
                        f"# Session result {data.id}\n\n"
                        "## Standard output\n\n    (empty)\n\n"
                        "## Standard error\n\n"
                        "    {\n"
                        '      "type": "ProviderModelNotFoundError",\n'
                        '      "message": "Model not found",\n'
                        '      "model": "opencode/deepseek-v4-flash-free"\n'
                        "    }"
                    ),
                )
            )
            (path / "RESULT.md").write_text(result, encoding="utf-8")
            (path / "SUMMARY.md").write_text("# failed\n", encoding="utf-8")
            record = SimpleNamespace(
                id=data.id,
                status="failed",
                path=str(path),
                retry_of=getattr(data, "retry_of", None),
                exit_code=70,
                created_at="2026-09-23T00:00:00Z",
            )
            self.sessions.append(record)
            raise RuntimeError("Session runner exited with code 70")

    workspace = FailingWorkspace(tmp_path)

    with pytest.raises(ExecutorLaunchError, match="Model not found") as captured:
        launch_inception_executor(
            tmp_path,
            runtime=runtime("opencode"),
            handoff_path=handoff(tmp_path),
            swarm_id="delivery",
            work_id="issue-14",
            workspace_factory=lambda cwd: workspace,
        )

    assert captured.value.recoverable is True
    assert "Provider error: }" not in str(captured.value)
