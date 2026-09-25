"""Governed Construction executor for Agora Flow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from agora.model import StartSessionInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.construction_reconciliation import reconcile_construction_execution
from agora_ai_sdlc.execution_bundle import build_execution_bundle, resolve_work_workspace
from agora_ai_sdlc.executor_launch import (
    ExecutorLaunchError,
    _bounded_output,
    _matching_sessions,
    _session_failure_diagnostic,
    _session_output,
    build_runtime_runner,
)
from agora_ai_sdlc.guided_execution import _construction_relevant_changes
from agora_ai_sdlc.local_delivery import diff_project_file_snapshots, project_file_snapshot
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes

CONSTRUCTION_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class ConstructionExecutionResult:
    session_id: str
    status: str
    result_path: str
    summary_path: str
    output: str
    reused: bool
    exit_code: int | None

    def snapshot(self) -> dict:
        return asdict(self)


def runtime_for_actor(
    root: Path,
    actor_reference: str,
    *,
    requested: str | None = None,
) -> RuntimeDiscovery:
    """Resolve a responsive repository executor from the assigned actor or override."""

    runtime_id = requested
    if runtime_id is None and actor_reference.startswith("project:ai-"):
        runtime_id = actor_reference.removeprefix("project:ai-")
    if runtime_id is None:
        raise ExecutorLaunchError(
            "Construction cannot infer the selected AI runtime from the assigned developer actor."
        )

    for runtime in discover_runtimes(root):
        if runtime.id == runtime_id and runtime.installed and runtime.responsive:
            return runtime
    raise ExecutorLaunchError(f"Construction runtime {runtime_id!r} is not installed and responsive.")


def _construction_prompt(root: Path, bundle_path: Path, swarm_id: str, work_id: str) -> str:
    try:
        bundle = bundle_path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ExecutorLaunchError(f"Construction bundle is outside the governed project root: {bundle_path}") from error

    return (
        "Run Agora Flow Construction for the current governed Work. "
        f"The governed project root is exactly {root.resolve()}. "
        f"Read {bundle} first; it is the deterministic bounded execution context. "
        "Then read .agora/skills/agora-ai-sdlc-guided/references/construction.md. "
        f"The governed scope is swarm={swarm_id}, work={work_id}. "
        "Before changing files, verify the current working directory resolves to the governed "
        "project root. Do not broaden repository inspection unless the execution bundle leaves an "
        "explicit unresolved need. Implement only the approved scope and acceptance criteria. "
        "Prepare the required Construction artifacts through the repository and register them "
        "through Agora Core when the installed contracts require registration. Run deterministic "
        "verification using aisdlc verify --run when authorized and record evidence through Core. "
        "Never fabricate criterion satisfaction, approval, evidence, or human authority. "
        "Do not transition lifecycle state and do not approve any role. Stop after the bounded "
        "Construction work and verification evidence are prepared for review. "
        "Your final response must concisely state files changed, verification performed, evidence "
        "recorded, remaining blockers, and the next human-governed decision."
    )


def _result(record, *, reused: bool) -> ConstructionExecutionResult:
    session_path = Path(record.path)
    output = _session_output(session_path) if record.status == "completed" else ""
    return ConstructionExecutionResult(
        session_id=record.id,
        status=record.status,
        result_path=str(session_path / "RESULT.md"),
        summary_path=str(session_path / "SUMMARY.md"),
        output=_bounded_output(output),
        reused=reused,
        exit_code=getattr(record, "exit_code", None),
    )


def launch_construction_executor(
    root: Path,
    *,
    swarm_id: str,
    work_id: str,
    actor_reference: str,
    runtime: RuntimeDiscovery | None = None,
    runtime_id: str | None = None,
    model: str | None = None,
    workspace_factory=AgoraWorkspace,
    decision=None,
) -> ConstructionExecutionResult:
    """Launch one governed Construction session.

    A previously completed session never short-circuits a launch: the Work is
    still in Construction, so that session produced no accepted progress.
    When ``decision`` is given, a successful exit without a relevant
    source/test/build delta or governed progress fails closed.
    """

    root = resolve_work_workspace(root.resolve(), work_id)
    bundle = build_execution_bundle(root, swarm=swarm_id, work=work_id, persist=True)
    if bundle.stage != "construction":
        raise ExecutorLaunchError(f"Construction executor requires Work state 'construction', found {bundle.stage!r}.")
    if bundle.json_path is None:
        raise ExecutorLaunchError("Construction execution bundle was not persisted.")

    runtime = runtime or runtime_for_actor(root, actor_reference, requested=runtime_id)
    prompt = _construction_prompt(root, Path(bundle.json_path), swarm_id, work_id)
    runner = build_runtime_runner(runtime, root, prompt, model=model)
    workspace = workspace_factory(cwd=root)

    base_id = f"ai-sdlc-construction-{work_id}"
    sessions = _matching_sessions(workspace, root, base_id)
    latest = sessions[-1] if sessions else None
    if latest is not None and latest.status == "running":
        raise ExecutorLaunchError(f"Construction executor session {latest.id} is already running.")

    session_id = base_id
    retry_of = None
    if latest is not None and latest.status == "failed":
        session_id = f"{base_id}-retry-{len(sessions) + 1}"
        retry_of = latest.id
    elif latest is not None and latest.status == "completed":
        # Core only accepts retries of failed sessions; a completed session
        # that left the Work in Construction is superseded by a fresh run.
        session_id = f"{base_id}-rerun-{len(sessions) + 1}"

    fields = getattr(StartSessionInput, "__dataclass_fields__", {})
    kwargs = {
        "actor_id": actor_reference,
        "swarm_id": swarm_id,
        "id": session_id,
        "work_id": work_id,
        "runner": runner,
        "launch": True,
    }
    if "timeout_seconds" in fields:
        kwargs["timeout_seconds"] = CONSTRUCTION_TIMEOUT_SECONDS
    if "executor_id" in fields:
        # Runtime choice is not an authority handoff; a synthetic ai-<runtime>
        # id is rejected by Core when that actor is not registered.
        kwargs["executor_id"] = actor_reference.removeprefix("project:")
    if "retry_of" in fields and retry_of is not None:
        kwargs["retry_of"] = retry_of
    if "runtime_version" in fields and runtime.version:
        kwargs["runtime_version"] = runtime.version

    before_snapshot = project_file_snapshot(root) if decision is not None else {}
    try:
        completed = workspace.start_session(StartSessionInput(**kwargs))
    except (OSError, RuntimeError, ValueError) as error:
        after = _matching_sessions(workspace, root, base_id)
        durable = after[-1] if after else None
        suffix = ""
        if durable is not None:
            diagnostic = _session_failure_diagnostic(Path(durable.path))
            if diagnostic:
                suffix = f" Executor diagnostic: {diagnostic}."
            suffix += f" Durable diagnostics: {Path(durable.path) / 'SUMMARY.md'}."
        raise ExecutorLaunchError(
            f"Construction executor {runtime.name} failed: {error}.{suffix}",
            recoverable=True,
        ) from error

    if completed.status != "completed":
        raise ExecutorLaunchError(
            f"Construction executor {runtime.name} ended with unexpected session status {completed.status!r}"
        )
    if decision is not None:
        try:
            reconciliation = reconcile_construction_execution(root, decision, workspace_factory=workspace_factory)
        except (OSError, RuntimeError, ValueError) as error:
            raise ExecutorLaunchError(
                f"Construction executor {runtime.name} completed, but reconciliation failed: {error}"
            ) from error
        changes = diff_project_file_snapshots(before_snapshot, project_file_snapshot(root))
        governed = bool(
            reconciliation.registered_artifacts or reconciliation.criterion_stages or reconciliation.verification_passed
        )
        if not _construction_relevant_changes(changes) and not governed:
            raise ExecutorLaunchError(
                f"Construction executor {runtime.name} exited successfully but produced no observable "
                "source/test/build-config change and no governed Construction progress."
            )
    return _result(completed, reused=False)
