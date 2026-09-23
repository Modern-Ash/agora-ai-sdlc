"""Provider-neutral governed executor launch for Agora Flow Inception."""

from __future__ import annotations

import shlex
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from agora.markdown import read_markdown
from agora.model import LaunchSessionInput, StartSessionInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery

SCHEMA = "agora-ai-sdlc/executor-adapters/v1"
MAX_PRESENTATION_CHARS = 6000


class ExecutorLaunchError(ValueError):
    """Stable launch failure surfaced by the Start happy path."""


@dataclass(frozen=True)
class ExecutorAdapter:
    id: str
    kind: str
    argv: tuple[str, ...]
    guidance: str | None = None


@dataclass(frozen=True)
class InceptionExecutionResult:
    session_id: str
    status: str
    result_path: str
    summary_path: str
    output: str
    reused: bool
    retry_of: str | None
    exit_code: int | None

    def snapshot(self) -> dict:
        return asdict(self)


def load_executor_adapters() -> dict[str, ExecutorAdapter]:
    path = asset_root("profiles") / "executors.yaml"
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ExecutorLaunchError(f"Cannot load executor adapters: {path}") from error
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ExecutorLaunchError(f"Invalid executor adapter registry: {path}")
    raw = payload.get("executors")
    if not isinstance(raw, dict) or not raw:
        raise ExecutorLaunchError("Executor adapter registry is empty")

    adapters: dict[str, ExecutorAdapter] = {}
    for runtime_id, data in raw.items():
        if not isinstance(runtime_id, str) or not runtime_id or not isinstance(data, dict):
            raise ExecutorLaunchError("Executor adapter registry contains an invalid entry")
        kind = data.get("kind")
        if kind not in {"agent", "provider"}:
            raise ExecutorLaunchError(f"Executor adapter {runtime_id!r} has unsupported kind {kind!r}")
        argv_raw = data.get("argv", [])
        if not isinstance(argv_raw, list) or any(not isinstance(item, str) or not item for item in argv_raw):
            raise ExecutorLaunchError(f"Executor adapter {runtime_id!r} argv must be a string list")
        if kind == "agent" and not argv_raw:
            raise ExecutorLaunchError(f"Executor adapter {runtime_id!r} must declare argv")
        guidance = data.get("guidance")
        if guidance is not None and (not isinstance(guidance, str) or not guidance.strip()):
            raise ExecutorLaunchError(f"Executor adapter {runtime_id!r} guidance must be text")
        adapters[runtime_id] = ExecutorAdapter(runtime_id, kind, tuple(argv_raw), guidance)
    return adapters


def executor_capable(runtime_id: str) -> bool:
    adapter = load_executor_adapters().get(runtime_id)
    return adapter is not None and adapter.kind == "agent"


def _adapter(runtime_id: str) -> ExecutorAdapter:
    adapter = load_executor_adapters().get(runtime_id)
    if adapter is None:
        raise ExecutorLaunchError(f"No executor adapter is registered for runtime {runtime_id!r}")
    if adapter.kind != "agent":
        guidance = adapter.guidance or "Select a repository-capable agent runtime."
        raise ExecutorLaunchError(f"Runtime {runtime_id!r} is not a repository executor. {guidance}")
    return adapter


def _inception_prompt(root: Path, handoff_path: Path) -> str:
    root = root.resolve()
    handoff_path = handoff_path.resolve()
    try:
        handoff = handoff_path.relative_to(root)
    except ValueError as error:
        raise ExecutorLaunchError(f"Inception handoff is outside the governed project root: {handoff_path}") from error
    return (
        "Run Agora Flow Inception for the current governed Work. "
        f"The governed project root is exactly {root}. "
        f"Read and follow {handoff} as the execution contract and read AGORA_CONTEXT when available. "
        "Before any work, verify the current working directory resolves to the governed project root; "
        "if it does not, stop without changing files. "
        "Stay in Inception: inspect only bounded relevant context, prepare the Level 1 Plan, cohesive Units "
        "and useful Bolts, trace acceptance criteria, identify risks/constraints/dependencies, and persist "
        "non-authoritative proposal artifacts only where the installed AI-SDLC contracts permit. "
        "Do not implement product code, do not enter Construction, and do not infer or fabricate human approval. "
        "Finish with a concise proposal and an explicit human decision required to continue."
    )


def build_executor_runner(runtime: RuntimeDiscovery, root: Path, handoff_path: Path) -> str:
    adapter = _adapter(runtime.id)
    executable = runtime.executable or runtime.command
    prompt = _inception_prompt(root, handoff_path)
    values = {"executable": executable, "prompt": prompt}
    try:
        argv = [part.format(**values) for part in adapter.argv]
    except KeyError as error:
        raise ExecutorLaunchError(
            f"Executor adapter {runtime.id!r} references unknown placeholder {error.args[0]!r}"
        ) from error
    if not argv or Path(argv[0]).name != Path(executable).name:
        raise ExecutorLaunchError(f"Executor adapter {runtime.id!r} produced an invalid launch command")
    return shlex.join(argv)


def _bounded_output(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_PRESENTATION_CHARS:
        return text
    head = text[:1000].rstrip()
    tail = text[-(MAX_PRESENTATION_CHARS - 1100) :].lstrip()
    return f"{head}\n\n… output abbreviated; durable RESULT.md retains the bounded transcript …\n\n{tail}"


def _session_output(path: Path) -> str:
    result_path = path / "RESULT.md"
    if not result_path.is_file():
        raise ExecutorLaunchError(f"Executor session result is missing: {result_path}")
    document = read_markdown(result_path)
    body = document.body
    start = body.find("## Standard output")
    end = body.find("## Standard error")
    if start < 0:
        return ""
    stdout = body[start + len("## Standard output") : end if end >= 0 else None].strip("\n")
    lines = []
    for line in stdout.splitlines():
        lines.append(line[4:] if line.startswith("    ") else line)
    value = "\n".join(lines).strip()
    return "" if value == "(empty)" else _bounded_output(value)


def _result(record, *, reused: bool) -> InceptionExecutionResult:
    session_path = Path(record.path)
    return InceptionExecutionResult(
        session_id=record.id,
        status=record.status,
        result_path=str(session_path / "RESULT.md"),
        summary_path=str(session_path / "SUMMARY.md"),
        output=_session_output(session_path) if record.status == "completed" else "",
        reused=reused,
        retry_of=getattr(record, "retry_of", None),
        exit_code=getattr(record, "exit_code", None),
    )


def _matching_sessions(workspace: AgoraWorkspace, base_id: str) -> list:
    matches = [
        session
        for session in workspace.list_sessions()
        if session.id == base_id or session.id.startswith(base_id + "-retry-")
    ]
    return sorted(matches, key=lambda item: (getattr(item, "created_at", ""), item.id))


def _retry_id(base_id: str, sessions: list) -> str:
    used = {item.id for item in sessions}
    number = 2
    while f"{base_id}-retry-{number}" in used:
        number += 1
    return f"{base_id}-retry-{number}"


def launch_inception_executor(
    root: Path,
    *,
    runtime: RuntimeDiscovery,
    handoff_path: Path,
    swarm_id: str,
    work_id: str,
    responsible_actor: str = "product-owner",
    workspace_factory=AgoraWorkspace,
) -> InceptionExecutionResult:
    """Launch one governed Inception session and reuse completed work idempotently."""

    root = root.resolve()
    runner = build_executor_runner(runtime, root, handoff_path)
    workspace = workspace_factory(cwd=root)
    executor_id = f"ai-{runtime.id}"
    base_id = f"ai-sdlc-inception-{work_id}"
    sessions = _matching_sessions(workspace, base_id)
    latest = sessions[-1] if sessions else None

    if latest is not None and latest.status == "completed":
        return _result(latest, reused=True)
    if latest is not None and latest.status == "running":
        raise ExecutorLaunchError(
            f"Inception executor session {latest.id} is already running; inspect its durable session state instead of launching a duplicate."
        )
    if latest is not None and latest.status == "prepared":
        try:
            completed = workspace.launch_session(LaunchSessionInput(session_id=latest.id))
        except (OSError, RuntimeError, ValueError) as error:
            raise ExecutorLaunchError(f"Inception executor failed while launching prepared session {latest.id}: {error}") from error
        return _result(completed, reused=False)

    session_id = base_id
    retry_of = None
    if latest is not None and latest.status == "failed":
        session_id = _retry_id(base_id, sessions)
        retry_of = latest.id

    fields = getattr(StartSessionInput, "__dataclass_fields__", {})
    kwargs = {
        "actor_id": responsible_actor,
        "swarm_id": swarm_id,
        "id": session_id,
        "work_id": work_id,
        "runner": runner,
        "launch": True,
    }
    if "executor_id" in fields:
        kwargs["executor_id"] = executor_id
    if "retry_of" in fields and retry_of is not None:
        kwargs["retry_of"] = retry_of
    if "runtime_version" in fields and runtime.version:
        kwargs["runtime_version"] = runtime.version

    try:
        completed = workspace.start_session(StartSessionInput(**kwargs))
    except (OSError, RuntimeError, ValueError) as error:
        latest_after = _matching_sessions(workspace, base_id)
        durable = latest_after[-1] if latest_after else None
        suffix = (
            f" Durable diagnostics: {Path(durable.path) / 'SUMMARY.md'}."
            if durable is not None
            else ""
        )
        raise ExecutorLaunchError(f"Inception executor {runtime.name} failed: {error}.{suffix}") from error

    if completed.status != "completed":
        raise ExecutorLaunchError(
            f"Inception executor {runtime.name} ended with unexpected session status {completed.status!r}"
        )
    return _result(completed, reused=False)
