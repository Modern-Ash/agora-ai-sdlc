"""Governed execution of one guided, non-authoritative AI-SDLC preparation step."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread

from agora.model import StartSessionInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.construction_reconciliation import (
    prepare_construction_scaffold,
    reconcile_construction_execution,
)
from agora_ai_sdlc.execution_bundle import build_execution_bundle
from agora_ai_sdlc.execution_context import persist_execution_context, select_execution_context
from agora_ai_sdlc.execution_economics import record_executor_event
from agora_ai_sdlc.executor_launch import ExecutorLaunchError, _session_failure_diagnostic, build_runtime_runner
from agora_ai_sdlc.guided import GuidedDecision, inspect_next
from agora_ai_sdlc.laya_provider import LayaDecisionProvider, LayaUnavailable
from agora_ai_sdlc.local_delivery import diff_project_file_snapshots, project_file_snapshot
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.runtime_execution import (
    RuntimeExecutionError,
    build_governed_runtime_plan,
    supports_governed_runtime_plan,
)
from agora_ai_sdlc.skill_planner import maybe_plan_skill
from agora_ai_sdlc.verification import persisted_verification_diagnostic
from agora_ai_sdlc.wizard import load_answers

_CONSTRUCTION_SOURCE_SUFFIXES = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".java",
    ".kt",
    ".go",
    ".rs",
}
_CONSTRUCTION_BUILD_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "requirements.txt",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "cargo.toml",
    "go.mod",
}


def _construction_relevant_changes(paths: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for path in paths:
        candidate = Path(path)
        name = candidate.name.casefold()
        if candidate.suffix.casefold() in _CONSTRUCTION_SOURCE_SUFFIXES or name in _CONSTRUCTION_BUILD_FILES:
            values.append(path)
    return tuple(values)


@dataclass(frozen=True)
class GuidedExecutionResult:
    session_id: str
    status: str
    result_path: str
    runtime: str
    execution_tier: str | None = None
    selection_reason: str | None = None
    planner_tier: str | None = None
    planner_path: str | None = None
    planner_reused: bool = False


def _runtime(root: Path, runtime_id: str) -> RuntimeDiscovery:
    for item in discover_runtimes(root):
        if item.id == runtime_id and item.installed and item.responsive:
            return item
    raise ExecutorLaunchError(f"Selected runtime {runtime_id!r} is no longer responsive")


def _runner(runtime: RuntimeDiscovery, root: Path, prompt: str, model: str | None) -> str:
    """Legacy/minimal-Core compatibility seam. Full Core uses ExecutionEnvelope adapters."""
    return build_runtime_runner(runtime, root, prompt, model=model)


def _prompt(root: Path, decision: GuidedDecision, bundle_path: str | None) -> str:
    skill = root / ".agora" / "skills" / "agora-ai-sdlc-guided" / "SKILL.md"
    parts = [
        "Execute exactly one safe guided AI-SDLC preparation iteration for the current governed Work.",
        f"Project root: {root.resolve()}.",
        f"Work: {decision.swarm}/{decision.work}. Stage: {decision.state or 'unknown'}.",
        (
            "Canonical Agora scope for this entire iteration is "
            f"--swarm {decision.swarm} --work {decision.work}. "
            "Every Agora/aisdlc command that accepts Work scope MUST include both identifiers explicitly. "
            "Never rely on the default delivery swarm or infer another Work from its id."
        ),
        (
            f"Read and follow the guided skill at {skill}."
            if decision.state != "construction"
            else "Agora Flow supplies the required Construction guidance directly in this prompt. "
            "Do not discover or glob .agora paths to recover instructions already supplied by the host."
        ),
        (
            "The governed project root above is the complete working boundary for this iteration. "
            "Do not inspect, grep, read, or modify the Agora AI-SDLC installation, its Python package, "
            "another checkout, or any path outside the governed project root. "
            + (
                "If anything is unclear, rely on the host-supplied Construction context in this prompt; "
                "do not discover hidden .agora files."
                if decision.state == "construction"
                else "If an installed contract appears unclear, use only the project-local .agora skill/method resources."
            )
        ),
    ]
    if bundle_path:
        bundle_text = ""
        if decision.state == "construction":
            try:
                bundle_candidate = Path(bundle_path)
                if bundle_candidate.is_file():
                    bundle_text = bundle_candidate.read_text(encoding="utf-8").strip()
            except (OSError, ValueError):
                bundle_text = ""
        if bundle_text:
            parts.append(
                "Host-supplied bounded execution context. Treat its selected paths as the preferred reading set; "
                "protected/uncertain paths are retained deliberately:\n" + bundle_text[:12000]
            )
        else:
            parts.append(
                f"Use the bounded execution context at {bundle_path}. "
                "Treat its selected paths as the preferred reading set; protected/uncertain paths are retained deliberately."
            )
    if decision.messages:
        parts.append("Current obligations: " + " | ".join(decision.messages))
    if decision.state == "construction":
        construction_guidance_path = (
            root / ".agora" / "skills" / "agora-ai-sdlc-guided" / "references" / "construction.md"
        )
        try:
            construction_guidance = construction_guidance_path.read_text(encoding="utf-8").strip()
        except OSError:
            construction_guidance = ""
        if construction_guidance:
            parts.append("Host-supplied Construction phase guidance:\n" + construction_guidance[:8000])
        exact = []
        if decision.missing_artifacts:
            exact.append("missing artifacts=" + ", ".join(decision.missing_artifacts))
        if decision.missing_evidence:
            exact.append("missing evidence=" + ", ".join(decision.missing_evidence))
        if decision.unsatisfied_criteria:
            exact.append("unsatisfied criteria=" + ", ".join(decision.unsatisfied_criteria))
        artifact_root = root / ".agora" / "ai-sdlc" / "construction" / decision.work
        task_path = artifact_root / "CONSTRUCTION-TASK.md"
        task_text = ""
        try:
            task_text = task_path.read_text(encoding="utf-8").strip()
        except OSError:
            task_text = ""
        if task_text:
            parts.append(
                "Host-supplied Construction task (authoritative for this repair iteration):\n" + task_text[:8000]
            )

        diagnostic = persisted_verification_diagnostic(root, decision.work)
        if diagnostic:
            parts.append(
                "Host-supplied deterministic verification diagnosis. Repair this concrete condition before finishing:\n"
                + diagnostic
            )
        parts.append(
            "Construction completion contract: " + ("; ".join(exact) if exact else "implementation pending") + ". "
            "The concrete Construction task content is supplied above when available. "
            "Do not search for that task under .agora/. "
            "Agora Flow has already materialized and registered the governance/design artifacts. "
            "Your responsibility in this iteration is implementation only: create actual product source files and executable "
            "automated tests outside .agora/, plus the minimal idiomatic build/test configuration needed to run them. "
            "Do not merely describe code in the final response; persist the files in the governed project root. "
            "Do NOT run Agora/Core mutation commands such as artifact add, evidence add, approval add, "
            "criterion-satisfy or lifecycle transition. Agora Flow host owns registration and criterion/evidence reconciliation "
            "after this process exits. A successful CLI process alone is not progress. "
            "Success checklist before exiting: persist a concrete source/test/build-config repair when verification is unresolved; "
            "ensure executable automated tests exist; ensure the project exposes a deterministic build/test command; "
            "never exit successfully after inspection-only or no-op work. "
            "Never record human approval or perform a lifecycle transition. "
            "If no safe repair can be persisted, report failure instead of claiming completion."
        )

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
                'after major outcomes with: agora session progress --session "$AGORA_SESSION_ID" '
                '--by "$AGORA_EXECUTOR" --summary "<milestone>". '
                "Good milestones describe facts such as context inspected, artifact persisted, or verification completed; "
                "never report chain-of-thought, private reasoning, prompts, secrets, or raw provider output."
            ),
            "Do not record human approval, do not change a human-owned decision, do not merge, deploy, or bypass a gate.",
            "Do not perform unrelated refactors. Minimize context and avoid reading files that the bounded bundle does not justify.",
            "Stop after the preparatory work is complete so Agora can re-read authoritative state.",
        ]
    )
    return " ".join(parts)


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
    execution_tier: str | None = None,
    repair_advice: str | None = None,
    workspace_factory=AgoraWorkspace,
    progress_fn: Callable[[str], None] | None = None,
) -> GuidedExecutionResult:
    """Run one bounded executor iteration and return to Core for re-inspection."""

    root = root.resolve()
    runtime = _runtime(root, runtime_id)

    if decision.state == "construction":
        prepare_construction_scaffold(
            root,
            decision,
            workspace_factory=workspace_factory,
        )
        refreshed = inspect_next(
            root,
            swarm=decision.swarm,
            work=decision.work,
        )
        if refreshed is not None and refreshed.state == "construction":
            decision = refreshed

    bundle = build_execution_bundle(
        root,
        swarm=decision.swarm,
        work=decision.work,
        persist=True,
    )
    if bundle.swarm != decision.swarm or bundle.work != decision.work:
        raise ExecutorLaunchError(
            "Guided execution scope changed before launch: "
            f"decision={decision.swarm}/{decision.work}, bundle={bundle.swarm}/{bundle.work}. "
            "Re-read Agora Core instead of executing stale context."
        )
    if bundle.stage != decision.state:
        raise ExecutorLaunchError(
            "Guided execution phase changed before launch: "
            f"decision={decision.state!r}, bundle={bundle.stage!r}. "
            "Re-read Agora Core instead of executing stale context."
        )
    workspace = workspace_factory(cwd=root)
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
    skill_plan = None
    if repair_advice is None:
        try:
            skill_plan = maybe_plan_skill(root, bundle, workspace=workspace)
        except (OSError, RuntimeError, ValueError):
            skill_plan = None

    prompt = _prompt(root, decision, str(lean_path) if lean_path is not None else bundle.markdown_path)
    if skill_plan is not None:
        prompt += (
            " Host-supplied read-only Skill Planner guidance follows. "
            "It is advisory, bounded to this Work, and does not replace verification or Core authority:\n"
            + skill_plan.text[:12000]
        )
    if repair_advice:
        prompt += (
            " Host-supplied diagnostic advice from a read-only escalation advisor follows. "
            "Treat it as non-authoritative repair guidance; verify it before applying and keep the same governed scope:\n"
            + repair_advice[:8000]
        )
    repair_diagnostic = (
        persisted_verification_diagnostic(root, decision.work) if decision.state == "construction" else None
    )
    before_snapshot = project_file_snapshot(root) if decision.state == "construction" else {}
    plan = None
    if supports_governed_runtime_plan(workspace):
        try:
            plan = build_governed_runtime_plan(
                root,
                decision=decision,
                bundle=bundle,
                runtime_id=runtime.id,
                model=model,
                runtime=runtime,
                workspace=workspace,
                actor=decision.actor,
                context={
                    "purpose": "guided-preparation",
                    "guidance": prompt,
                    "bounded_context": str(lean_path) if lean_path is not None else bundle.markdown_path,
                    **(
                        {
                            "routing": {
                                "profile": "cheap-first",
                                "tier": execution_tier,
                                "reason": "guided-selected",
                            }
                        }
                        if execution_tier
                        else {}
                    ),
                    **({"repair_advice": "bounded-escalation-advice"} if repair_advice else {}),
                    **(
                        {
                            "skill_planner": {
                                "tier": skill_plan.tier,
                                "path": str(Path(skill_plan.path).resolve().relative_to(root)),
                                "reused": skill_plan.reused,
                            }
                        }
                        if skill_plan is not None
                        else {}
                    ),
                },
            )
        except RuntimeExecutionError as error:
            raise ExecutorLaunchError(str(error)) from error
        runner = plan.runner
    else:
        runner = _runner(runtime, root, prompt, model)

    safe_stage = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (bundle.stage or "step"))
    base_id = f"ai-sdlc-guided-{decision.work}-{safe_stage}"
    session_id = base_id
    existing = {getattr(item, "id", "") for item in workspace.list_sessions()}
    suffix = 2
    while session_id in existing:
        session_id = f"{base_id}-{suffix}"
        suffix += 1

    actor_id = (
        plan.actor_id if plan is not None else (decision.actor or decision.role or "developer").removeprefix("project:")
    )
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
        assigned = plan.actor_id if plan is not None else (decision.actor or "").removeprefix("project:")
        if assigned:
            kwargs["executor_id"] = assigned
    if "runtime_version" in fields and runtime.version:
        kwargs["runtime_version"] = runtime.version
    if "timeout_seconds" in fields:
        kwargs["timeout_seconds"] = 600

    if progress_fn is not None:
        progress_fn("executor")
    record_executor_event(
        root,
        event="attempt",
        work=decision.work,
        swarm=decision.swarm,
        runtime=runtime,
        plan=plan,
        tier=execution_tier,
        model=model,
        workspace=workspace,
        reason=f"guided-{decision.state or 'unknown'}",
    )
    try:
        result = _start_session_with_heartbeat(
            workspace,
            StartSessionInput(**kwargs),
            progress_fn=progress_fn,
        )
    except (OSError, RuntimeError, ValueError) as error:
        session_path = root / ".agora" / "sessions" / session_id
        record_executor_event(
            root,
            event="failure",
            work=decision.work,
            swarm=decision.swarm,
            runtime=runtime,
            plan=plan,
            tier=execution_tier,
            model=model,
            workspace=workspace,
            reason=f"guided executor failure: {error}",
        )
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
        record_executor_event(
            root,
            event="failure",
            work=decision.work,
            swarm=decision.swarm,
            runtime=runtime,
            plan=plan,
            tier=execution_tier,
            model=model,
            workspace=workspace,
            reason=f"guided unexpected status: {getattr(result, 'status', None)!r}",
            exit_code=getattr(result, "exit_code", None),
        )
        raise ExecutorLaunchError(
            f"Guided executor {runtime.name} ended with unexpected status {getattr(result, 'status', None)!r}"
        )
    if decision.state == "construction":
        try:
            reconciliation = reconcile_construction_execution(
                root,
                decision,
                workspace_factory=workspace_factory,
            )
        except (OSError, RuntimeError, ValueError) as error:
            record_executor_event(
                root,
                event="failure",
                work=decision.work,
                swarm=decision.swarm,
                runtime=runtime,
                plan=plan,
                tier=execution_tier,
                model=model,
                workspace=workspace,
                reason=f"guided Construction reconciliation failure: {error}",
                exit_code=getattr(result, "exit_code", None),
            )
            raise ExecutorLaunchError(
                f"Guided executor {runtime.name} completed, but Construction reconciliation failed: {error}"
            ) from error

        after_snapshot = project_file_snapshot(root)
        changed_this_iteration = diff_project_file_snapshots(before_snapshot, after_snapshot)
        relevant_changes = _construction_relevant_changes(changed_this_iteration)
        governed_progress = bool(
            reconciliation.registered_artifacts or reconciliation.criterion_stages or reconciliation.verification_passed
        )
        if not relevant_changes and not governed_progress:
            diagnostic = repair_diagnostic or persisted_verification_diagnostic(root, decision.work)
            detail = f" Deterministic verification diagnosis: {diagnostic}" if diagnostic else ""
            record_executor_event(
                root,
                event="failure",
                work=decision.work,
                swarm=decision.swarm,
                runtime=runtime,
                plan=plan,
                tier=execution_tier,
                model=model,
                workspace=workspace,
                reason="guided Construction completed without observable governed progress",
                exit_code=getattr(result, "exit_code", None),
            )
            raise ExecutorLaunchError(
                f"Guided executor {runtime.name} exited successfully but produced no observable "
                f"source/test/build-config repair and no governed Construction progress.{detail}"
            )

    record_executor_event(
        root,
        event="success",
        work=decision.work,
        swarm=decision.swarm,
        runtime=runtime,
        plan=plan,
        tier=execution_tier,
        model=model,
        workspace=workspace,
        reason=f"guided-{decision.state or 'unknown'}",
        exit_code=getattr(result, "exit_code", None),
    )
    path = Path(result.path)
    return GuidedExecutionResult(
        session_id=result.id,
        status=result.status,
        result_path=str(path / "RESULT.md"),
        runtime=runtime.name,
        execution_tier=execution_tier,
        selection_reason="guided-selected" if execution_tier else None,
        planner_tier=skill_plan.tier if skill_plan is not None else None,
        planner_path=skill_plan.path if skill_plan is not None else None,
        planner_reused=skill_plan.reused if skill_plan is not None else False,
    )
