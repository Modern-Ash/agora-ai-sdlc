"""Governed execution of one guided, non-authoritative AI-SDLC preparation step."""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread

from agora.model import StartSessionInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.execution_bundle import build_execution_bundle
from agora_ai_sdlc.execution_context import persist_execution_context, select_execution_context
from agora_ai_sdlc.executor_launch import (
    ExecutorLaunchError,
    _session_failure_diagnostic,
    load_executor_adapters,
)
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.laya_provider import LayaDecisionProvider, LayaUnavailable
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.wizard import load_answers


@dataclass(frozen=True)
class GuidedExecutionResult:
    session_id: str
    status: str
    result_path: str
    runtime: str


def _runtime(root: Path, runtime_id: str) -> RuntimeDiscovery:
    for item in discover_runtimes(root):
        if item.id == runtime_id and item.installed and item.responsive:
            return item
    raise ExecutorLaunchError(f"Selected runtime {runtime_id!r} is no longer responsive")


def _prompt(root: Path, decision: GuidedDecision, bundle_path: str | None) -> str:
    skill = root / ".agora" / "skills" / "agora-ai-sdlc-guided" / "SKILL.md"
    parts = [
        "Execute exactly one safe guided AI-SDLC preparation iteration for the current governed Work.",
        f"Project root: {root.resolve()}.",
        f"Work: {decision.swarm}/{decision.work}. Stage: {decision.state or 'unknown'}.",
        f"Read and follow the guided skill at {skill}.",
    ]
    if bundle_path:
        parts.append(
            f"Use the bounded execution context at {bundle_path}. "
            "Treat its selected paths as the preferred reading set; protected/uncertain paths are retained deliberately."
        )
    if decision.messages:
        parts.append("Current obligations: " + " | ".join(decision.messages))
    answers = load_answers(root, decision.work)
    if answers:
        resolved = " | ".join(f"{key}={value}" for key, value in sorted(answers.items()))
        parts.append(
            "Human clarification answers collected by the Agora wizard: "
            + resolved
            + ". Treat these as explicit user-provided context; do not ask them again."
        )
    parts.extend(
        [
            (
                "Be proactive: inspect only the bounded relevant context, create or update the non-authoritative "
                "artifacts/evidence needed for the next gate, and run safe deterministic verification when useful."
            ),
            "Use existing Agora/Core commands and repository conventions instead of inventing lifecycle state.",
            (
                "When AGORA_SESSION_ID and AGORA_EXECUTOR are available, report only concise observable milestones "
                "after major outcomes with: agora session progress --session \"$AGORA_SESSION_ID\" "
                "--by \"$AGORA_EXECUTOR\" --summary \"<milestone>\". "
                "Good milestones describe facts such as context inspected, artifact persisted, or verification completed; "
                "never report chain-of-thought, private reasoning, prompts, secrets, or raw provider output."
            ),
            "Do not record human approval, do not change a human-owned decision, do not merge, deploy, or bypass a gate.",
            "Do not perform unrelated refactors. Minimize context and avoid reading files that the bounded bundle does not justify.",
            "Stop after the preparatory work is complete so Agora can re-read authoritative state.",
        ]
    )
    return " ".join(parts)


def _runner(runtime: RuntimeDiscovery, root: Path, prompt: str, model: str | None) -> str:
    adapter = load_executor_adapters().get(runtime.id)
    if adapter is None or adapter.kind != "agent":
        raise ExecutorLaunchError(f"Runtime {runtime.id!r} is not a repository executor")
    executable = runtime.executable or runtime.command
    values = {
        "executable": executable,
        "python": sys.executable,
        "root": str(root.resolve()),
        "model": model or "",
        "prompt": prompt,
    }
    argv = [part.format(**values) for part in adapter.argv]
    if runtime.id == "opencode" and not model:
        try:
            index = argv.index("--model")
        except ValueError:
            pass
        else:
            if index + 1 < len(argv) and argv[index + 1] == "":
                del argv[index : index + 2]
    return shlex.join(argv)


def _latest_session_progress(workspace, session_id: str) -> str | None:
    """Read the latest bounded executor milestone from Core's durable PROGRESS.md."""

    try:
        project_root = getattr(workspace, "project_root", None)
        root = Path(project_root()) if callable(project_root) else Path(workspace.cwd)
        path = root / ".agora" / "sessions" / session_id / "PROGRESS.md"
        if not path.is_file():
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
    except (AttributeError, OSError, TypeError, ValueError):
        return None

    for line in reversed(lines):
        if not line.startswith("- ") or " | " not in line:
            continue
        parts = line.split(" | ", 2)
        if len(parts) == 3:
            summary = parts[2].strip()
            return summary or None
    return None


def _start_session_with_heartbeat(
    workspace,
    data: StartSessionInput,
    *,
    progress_fn: Callable[[str], None] | None,
    interval_seconds: float = 15.0,
):
    """Run the synchronous Core session while keeping the terminal visibly alive."""

    if progress_fn is None or interval_seconds <= 0:
        return workspace.start_session(data)

    stop = Event()

    def emit_heartbeat() -> None:
        while not stop.wait(interval_seconds):
            summary = _latest_session_progress(workspace, data.id)
            progress_fn(f"executor_wait:{summary}" if summary else "executor_wait")

    thread = Thread(target=emit_heartbeat, name="agora-flow-heartbeat", daemon=True)
    thread.start()
    try:
        return workspace.start_session(data)
    finally:
        stop.set()
        thread.join(timeout=0.2)


def execute_guided_preparation(
    root: Path,
    decision: GuidedDecision,
    *,
    runtime_id: str,
    model: str | None = None,
    workspace_factory=AgoraWorkspace,
    progress_fn: Callable[[str], None] | None = None,
) -> GuidedExecutionResult:
    """Run one bounded executor iteration and return to Core for re-inspection."""

    root = root.resolve()
    runtime = _runtime(root, runtime_id)
    bundle = build_execution_bundle(
        root,
        swarm=decision.swarm,
        work=decision.work,
        persist=True,
    )
    lean_path = None
    if progress_fn is not None:
        progress_fn("context")
    try:
        lean = select_execution_context(
            root,
            bundle,
            provider=LayaDecisionProvider(),
        )
        lean_path = persist_execution_context(root, decision.work, lean)
    except (LayaUnavailable, OSError, RuntimeError, ValueError):
        lean = None
    prompt = _prompt(root, decision, str(lean_path) if lean_path is not None else bundle.markdown_path)
    runner = _runner(runtime, root, prompt, model)
    workspace = workspace_factory(cwd=root)

    safe_stage = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (decision.state or "step"))
    base_id = f"ai-sdlc-guided-{decision.work}-{safe_stage}"
    session_id = base_id
    existing = {getattr(item, "id", "") for item in workspace.list_sessions()}
    suffix = 2
    while session_id in existing:
        session_id = f"{base_id}-{suffix}"
        suffix += 1

    actor_id = (decision.actor or decision.role or "developer").removeprefix("project:")
    fields = getattr(StartSessionInput, "__dataclass_fields__", {})
    kwargs = {
        "actor_id": actor_id,
        "swarm_id": decision.swarm,
        "id": session_id,
        "work_id": decision.work,
        "runner": runner,
        "launch": True,
    }

    # Runtime selection is not an authority handoff. The Work's assigned actor
    # remains responsible even when Flow launches a different CLI/runtime.
    # Setting executor_id to a synthetic ai-<runtime> identity caused Core to
    # reject valid runtime switches when that actor was not registered.
    if "executor_id" in fields:
        assigned = (decision.actor or "").removeprefix("project:")
        if assigned:
            kwargs["executor_id"] = assigned
    if "runtime_version" in fields and runtime.version:
        kwargs["runtime_version"] = runtime.version
    if "timeout_seconds" in fields:
        kwargs["timeout_seconds"] = 600

    if progress_fn is not None:
        progress_fn("executor")
    try:
        result = _start_session_with_heartbeat(
            workspace,
            StartSessionInput(**kwargs),
            progress_fn=progress_fn,
        )
    except (OSError, RuntimeError, ValueError) as error:
        session_path = root / ".agora" / "sessions" / session_id
        diagnostic = ""
        try:
            diagnostic = _session_failure_diagnostic(session_path)
        except (OSError, ValueError):
            pass
        suffix = f" Executor diagnostic: {diagnostic}." if diagnostic else ""
        if "Durable diagnostics:" not in str(error):
            suffix += f" Durable diagnostics: {session_path / 'SUMMARY.md'}."
        raise ExecutorLaunchError(f"Guided executor {runtime.name} failed: {error}.{suffix}") from error

    if getattr(result, "status", None) != "completed":
        raise ExecutorLaunchError(
            f"Guided executor {runtime.name} ended with unexpected status {getattr(result, 'status', None)!r}"
        )
    path = Path(result.path)
    return GuidedExecutionResult(
        session_id=result.id,
        status=result.status,
        result_path=str(path / "RESULT.md"),
        runtime=runtime.name,
    )
