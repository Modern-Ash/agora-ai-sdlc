import time
from types import SimpleNamespace

import pytest

from agora_ai_sdlc.executor_launch import ExecutorLaunchError
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.guided_execution import _prompt, _start_session_with_heartbeat, execute_guided_preparation


def decision() -> GuidedDecision:
    return GuidedDecision(
        swarm="delivery",
        work="issue-26",
        title="Deliver issue",
        method="ai-sdlc",
        actor="project:ai-codex",
        role="developer",
        state="inception",
        target="construction",
        gate="inception-approved",
        blockers=("missing work",),
        messages=("Prepare missing artifacts.",),
        missing_artifacts=("plan",),
    )


def test_guided_prompt_requests_safe_durable_progress_milestones(monkeypatch, tmp_path):
    monkeypatch.setattr("agora_ai_sdlc.guided_execution.load_answers", lambda *args, **kwargs: {})

    prompt = _prompt(tmp_path, decision(), "repo://EXECUTION_BUNDLE.md")

    assert "agora session progress" in prompt
    assert "$AGORA_SESSION_ID" in prompt
    assert "$AGORA_EXECUTOR" in prompt
    assert "never report chain-of-thought" in prompt
    assert "--swarm delivery --work issue-26" in prompt


def test_runtime_switch_does_not_invent_executor_actor(monkeypatch, tmp_path):
    captured = {}
    progress = []

    runtime = SimpleNamespace(
        id="claude",
        name="Claude Code",
        installed=True,
        responsive=True,
        executable="/usr/bin/claude",
        command="claude",
        version="1.0",
    )
    monkeypatch.setattr("agora_ai_sdlc.guided_execution._runtime", lambda *args, **kwargs: runtime)
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_execution.build_execution_bundle",
        lambda *args, **kwargs: SimpleNamespace(
            markdown_path=str(tmp_path / "EXECUTION_BUNDLE.md"),
            swarm="delivery",
            work="issue-26",
            stage="inception",
        ),
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_execution.select_execution_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Laya unavailable in test")),
    )
    monkeypatch.setattr("agora_ai_sdlc.guided_execution._runner", lambda *args, **kwargs: "claude -p test")
    monkeypatch.setattr("agora_ai_sdlc.guided_execution.load_answers", lambda *args, **kwargs: {})

    class Workspace:
        def __init__(self, cwd):
            self.cwd = cwd

        def list_sessions(self):
            return []

        def start_session(self, data):
            captured["data"] = data
            return SimpleNamespace(
                id=data.id,
                status="completed",
                path=str(tmp_path / ".agora" / "sessions" / data.id),
            )

    result = execute_guided_preparation(
        tmp_path,
        decision(),
        runtime_id="claude",
        workspace_factory=Workspace,
        progress_fn=progress.append,
    )

    data = captured["data"]
    assert data.actor_id == "ai-codex"
    assert data.executor_id == "ai-codex"
    assert "claude" in data.runner
    assert result.runtime == "Claude Code"
    assert progress == ["context", "executor"]


def test_start_session_emits_latest_durable_milestone_while_waiting(tmp_path):
    progress = []
    session_id = "guided-progress-test"
    progress_path = tmp_path / ".agora" / "sessions" / session_id / "PROGRESS.md"
    progress_path.parent.mkdir(parents=True)
    progress_path.write_text(
        "# Session progress\n\n- 2026-09-24T22:00:00Z | executor=project:developer | Verification completed\n",
        encoding="utf-8",
    )

    class Workspace:
        cwd = tmp_path

        def start_session(self, data):
            time.sleep(0.03)
            return SimpleNamespace(status="completed")

    result = _start_session_with_heartbeat(
        Workspace(),
        SimpleNamespace(id=session_id),
        progress_fn=progress.append,
        interval_seconds=0.005,
    )

    assert result.status == "completed"
    assert "executor_wait:Verification completed" in progress


def test_guided_executor_failure_surfaces_durable_diagnostic(monkeypatch, tmp_path):
    runtime = SimpleNamespace(
        id="claude",
        name="Claude Code",
        installed=True,
        responsive=True,
        executable="/usr/bin/claude",
        command="claude",
        version="1.0",
    )
    monkeypatch.setattr("agora_ai_sdlc.guided_execution._runtime", lambda *args, **kwargs: runtime)
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_execution.build_execution_bundle",
        lambda *args, **kwargs: SimpleNamespace(
            markdown_path=str(tmp_path / "EXECUTION_BUNDLE.md"),
            swarm="delivery",
            work="issue-26",
            stage="inception",
        ),
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_execution.select_execution_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Laya unavailable in test")),
    )
    monkeypatch.setattr("agora_ai_sdlc.guided_execution._runner", lambda *args, **kwargs: "claude -p test")
    monkeypatch.setattr("agora_ai_sdlc.guided_execution.load_answers", lambda *args, **kwargs: {})

    class Workspace:
        def __init__(self, cwd):
            self.cwd = cwd

        def list_sessions(self):
            return []

        def start_session(self, data):
            path = self.cwd / ".agora" / "sessions" / data.id
            path.mkdir(parents=True, exist_ok=True)
            (path / "RESULT.md").write_text(
                """---
schema: agora/session-result/v1
session: test
status: failed
exit-code: 1
---
# Session result

## Standard output

    (empty)

## Standard error

    Bash tool permission denied in non-interactive mode
""",
                encoding="utf-8",
            )
            (path / "SUMMARY.md").write_text("# failed\n", encoding="utf-8")
            raise RuntimeError(f"Session runner exited with code 1: {data.id} (nonzero-exit)")

    with pytest.raises(ExecutorLaunchError, match="Bash tool permission denied") as captured:
        execute_guided_preparation(
            tmp_path,
            decision(),
            runtime_id="claude",
            workspace_factory=Workspace,
        )

    assert "Durable diagnostics:" in str(captured.value)


def test_construction_prompt_requires_observable_governed_progress(monkeypatch, tmp_path):
    monkeypatch.setattr("agora_ai_sdlc.guided_execution.load_answers", lambda *args, **kwargs: {})
    current = GuidedDecision(
        **{
            **decision().snapshot(),
            "state": "construction",
            "target": "operations",
            "gate": "construction-verified",
            "missing_artifacts": ("domain-model", "implementation-plan"),
            "missing_evidence": ("test-suite",),
            "unsatisfied_criteria": ("source-issue",),
        }
    )

    prompt = _prompt(tmp_path, current, "repo://EXECUTION_BUNDLE.md")

    assert "A successful CLI process alone is not progress" in prompt
    assert "missing artifacts=domain-model, implementation-plan" in prompt
    assert "missing evidence=test-suite" in prompt
    assert "unsatisfied criteria=source-issue" in prompt
    assert "Never record human approval or perform a lifecycle transition" in prompt
    assert "Construction phase guidance" in prompt


def test_guided_executor_refuses_scope_mismatch_before_runtime(monkeypatch, tmp_path):
    runtime = SimpleNamespace(
        id="claude",
        name="Claude Code",
        installed=True,
        responsive=True,
        executable="/usr/bin/claude",
        command="claude",
        version="1.0",
    )
    monkeypatch.setattr("agora_ai_sdlc.guided_execution._runtime", lambda *args, **kwargs: runtime)
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_execution.build_execution_bundle",
        lambda *args, **kwargs: SimpleNamespace(
            markdown_path=str(tmp_path / "EXECUTION_BUNDLE.md"),
            swarm="issue-99-delivery",
            work="issue-26",
            stage="inception",
        ),
    )

    with pytest.raises(ExecutorLaunchError, match="scope changed before launch"):
        execute_guided_preparation(tmp_path, decision(), runtime_id="claude")
