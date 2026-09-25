"""AI-SDLC aligned entry flow for starting real delivery work from an issue."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from agora.markdown import read_markdown
from agora.model import (
    CreateIntentInput,
    CreateWorkInput,
    InstallMethodInput,
    InstallToolAdapterInput,
    InvokeToolInput,
)
from agora.sdlc import SdlcService
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.deterministic_clarification import record_zero_question_clarification
from agora_ai_sdlc.deterministic_inception import build_deterministic_inception
from agora_ai_sdlc.executor_launch import (
    ExecutorLaunchError,
    InceptionExecutionResult,
    executor_capable,
    launch_inception_executor,
)
from agora_ai_sdlc.i18n import t
from agora_ai_sdlc.inception_handoff import write_inception_handoff
from agora_ai_sdlc.inception_materialization import materialize_deterministic_inception
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.start_preflight import (
    StartPreparationResult,
    ensure_start_ready,
    isolate_dirty_work,
)


class StartFlowError(ValueError):
    """Raised when the governed start flow cannot be prepared safely."""


class StartExecutorError(StartFlowError):
    """Executor failure that may support an interactive runtime/model recovery."""

    def __init__(
        self,
        message: str,
        *,
        runtime_id: str,
        workspace_root: str,
        recoverable: bool,
    ) -> None:
        super().__init__(message)
        self.runtime_id = runtime_id
        self.workspace_root = workspace_root
        self.recoverable = recoverable


@dataclass(frozen=True)
class StartFlowResult:
    project: str
    issue: int
    swarm_id: str
    issue_url: str
    issue_title: str
    intent_id: str
    intent_path: str
    work_id: str
    work_path: str
    base_branch: str | None
    branch: str | None
    pathway: str
    runtime_id: str
    runtime_name: str
    runtime_model: str | None
    tool_run_id: str
    handoff_path: str
    skill_path: str
    workspace_root: str
    workspace_isolated: bool
    preflight_actions: tuple[str, ...]
    executor_session_id: str | None = None
    executor_result_path: str | None = None
    executor_summary_path: str | None = None
    executor_output: str | None = None
    executor_reused: bool = False
    inception_mode: str = "prepared"
    inception_output: str | None = None
    deterministic_inception_path: str | None = None
    semantic_gaps: tuple[str, ...] = ()
    status: str = "inception-prepared"

    def snapshot(self) -> dict:
        return asdict(self)


def _run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise StartFlowError((result.stderr or "git command failed").strip())
    return result.stdout.strip()


def _git_succeeds(root: Path, *args: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _is_git_repository(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _default_base_branch(root: Path) -> str:
    """Resolve a local base branch without contacting the remote."""

    result = subprocess.run(
        ["git", "-C", str(root), "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip().startswith("origin/"):
        return result.stdout.strip().removeprefix("origin/")
    for candidate in ("main", "master"):
        if _git_succeeds(root, "show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"):
            return candidate
    return _run_git(root, "branch", "--show-current")


def _switch_clean(root: Path, branch: str) -> None:
    current = _run_git(root, "branch", "--show-current")
    if current == branch:
        return
    if _run_git(root, "status", "--porcelain"):
        raise StartFlowError(f"Cannot switch from {current!r} to {branch!r}: commit or stash local changes first")
    _run_git(root, "switch", branch)


def infer_project(root: Path) -> str:
    """Infer owner/repository from origin without contacting GitHub."""

    remote = _run_git(root, "remote", "get-url", "origin")
    patterns = (
        r"^git@github\.com:(?P<project>[^/]+/[^/]+?)(?:\.git)?$",
        r"^https://github\.com/(?P<project>[^/]+/[^/]+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/(?P<project>[^/]+/[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.match(pattern, remote)
        if match:
            return match.group("project")
    raise StartFlowError(f"Cannot infer GitHub project from origin: {remote}")


def _select_runtime(
    root: Path,
    requested: str | None,
    *,
    discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
) -> RuntimeDiscovery:
    found = discovery(root)
    available = [item for item in found if item.installed and item.responsive]
    if requested:
        for item in available:
            if item.id == requested:
                if not executor_capable(item.id):
                    raise StartFlowError(
                        f"Requested runtime {requested!r} is not a repository executor. "
                        "Use an agent host such as OpenCode and configure its model provider separately."
                    )
                return item
        raise StartFlowError(f"Requested AI runtime {requested!r} is not installed and responsive")
    available = [item for item in available if executor_capable(item.id)]
    configured = [item for item in available if item.configured]
    if configured:
        return configured[0]
    if available:
        return available[0]
    raise StartFlowError(
        "No responsive repository-capable AI executor was detected. "
        "Install or configure OpenCode, Codex, or Claude Code. "
        "Ollama alone is a model provider, not the repository executor."
    )


_LEGACY_PRODUCT_OWNER_TOOL_CAPABILITIES = (
    'allowed-tool-capabilities: ["repository.read", "repository.governance.read", "docs.read", "docs.write"]'
)


def _ensure_issue_read_capability(workspace: AgoraWorkspace, root: Path) -> None:
    """Repair only the known packaged Product Owner role that predates issue.read."""

    role = root / ".agora" / "methods" / "ai-sdlc" / "roles" / "product-owner.md"
    if not role.is_file():
        return
    content = role.read_text(encoding="utf-8")
    if '"issue.read"' in content:
        return
    if _LEGACY_PRODUCT_OWNER_TOOL_CAPABILITIES not in content:
        return

    source = asset_root("registry") / "method-versions" / "ai-sdlc" / "0.2.0"
    packaged_role = source / "roles" / "product-owner.md"
    if not packaged_role.is_file() or '"issue.read"' not in packaged_role.read_text(encoding="utf-8"):
        raise StartFlowError("Packaged AI-SDLC Product Owner role cannot read issues")
    workspace.install_method(
        InstallMethodInput(
            source=str(source),
            scope="project",
            force=True,
        )
    )


def _configured_pathway(root: Path) -> str:
    metadata = root / "ai-sdlc" / "project.yaml"
    if metadata.is_file():
        try:
            payload = yaml.safe_load(metadata.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            payload = {}
        pathway = payload.get("pathway")
        if isinstance(pathway, str) and pathway:
            return pathway
    return "new-product"


def _select_pathway(root: Path, payload: dict) -> str:
    """Select a deterministic low-ceremony pathway from explicit source scope."""

    title = str(payload.get("title") or "").strip().casefold()
    body = str(payload.get("body") or "").casefold()
    documentation_only = (
        "documentation-only" in body
        or "do not implement" in body
        or "no implement" in body
        or (title.startswith(("define ", "document ")) and ".md" in body)
    )
    return "documentation" if documentation_only else _configured_pathway(root)


def _ensure_issue_work(
    workspace: AgoraWorkspace,
    root: Path,
    *,
    swarm: str,
    actor: str,
    issue: int,
    issue_url: str,
):
    """Create/reuse one governed Work and Core-owned branch for the issue."""

    work_id = f"issue-{issue}"
    existing = next((item for item in workspace.list_work(swarm_id=swarm) if item.id == work_id), None)
    if existing is not None:
        existing_branch = getattr(existing, "branch", None)
        if existing_branch and _is_git_repository(root):
            current = _run_git(root, "branch", "--show-current")
            if current != existing_branch:
                if _run_git(root, "status", "--porcelain"):
                    raise StartFlowError(f"Cannot switch to Work branch {existing_branch!r} with local changes present")
                _run_git(root, "switch", existing_branch)
        return existing

    branch = f"ai-sdlc/issue-{issue}"
    common = {
        "swarm_id": swarm,
        "id": work_id,
        "title": f"Deliver GitHub issue #{issue}",
        "actor_id": actor,
        "acceptance_criteria": [("source-issue", f"Satisfy the acceptance criteria from GitHub issue #{issue}")],
        "description": f"Source issue: {issue_url}",
    }
    fields = getattr(CreateWorkInput, "__dataclass_fields__", {})
    if {"branch", "create_branch"} <= set(fields) and _is_git_repository(root):
        base_branch = _default_base_branch(root)
        local_branch = _git_succeeds(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
        remote_branch = _git_succeeds(root, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}")
        if local_branch:
            _switch_clean(root, branch)
            return workspace.create_work(
                CreateWorkInput(
                    **common,
                    base_branch=base_branch,
                    branch=branch,
                    create_branch=False,
                )
            )
        if remote_branch:
            _switch_clean(root, base_branch)
            _run_git(root, "switch", "-c", branch, "--track", f"origin/{branch}")
            return workspace.create_work(
                CreateWorkInput(
                    **common,
                    base_branch=base_branch,
                    branch=branch,
                    create_branch=False,
                )
            )
        _switch_clean(root, base_branch)
        return workspace.create_work(
            CreateWorkInput(
                **common,
                base_branch=base_branch,
                branch=branch,
                create_branch=True,
            )
        )
    return workspace.create_work(CreateWorkInput(**common))


def _first_invalid_governed_markdown(root: Path, paths: list[Path]) -> tuple[Path, str] | None:
    for path in paths:
        if not path.is_file():
            continue
        try:
            read_markdown(path)
        except (OSError, ValueError) as error:
            return path, str(error)
    return None


def _diagnose_issue_read_markdown(root: Path, run_id: str) -> str | None:
    candidates = [
        root / ".agora" / "project.md",
        root / ".agora" / "methods" / "ai-sdlc" / "roles" / "product-owner.md",
        root / ".agora" / "tools" / "github-issues" / "TOOL.md",
        root / ".agora" / "tools" / "github-issues" / "operations" / "view.md",
        root / ".agora" / "actors" / "product-owner.md",
        root / ".agora" / "tool-runs" / run_id / "RUN.md",
        root / ".agora" / "tool-runs" / run_id / "RESULT.md",
    ]
    broken = _first_invalid_governed_markdown(root, candidates)
    if broken is None:
        return None
    path, detail = broken
    return f"{path.relative_to(root)}: {detail}"


def _get_target_intent(workspace: AgoraWorkspace, root: Path, intent_id: str):
    """Load exactly one Intent without scanning unrelated durable history."""

    getter = getattr(workspace, "get_intent", None)
    if callable(getter):
        return getter(intent_id)
    return SdlcService(root).get_intent(intent_id)


def _issue_payload(workspace: AgoraWorkspace, run_id: str) -> dict:
    inspection = workspace.show_tool_run(run_id)
    result = inspection.result
    if result is None:
        raise StartFlowError(f"Governed issue read {run_id} has no result")
    if result.status != "completed":
        raise StartFlowError(result.stderr or f"Governed issue read {run_id} failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise StartFlowError("GitHub issue adapter returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise StartFlowError("GitHub issue adapter returned an unexpected payload")
    return payload


def prepare_start(
    root: Path,
    *,
    issue: int,
    project: str | None = None,
    agent: str | None = None,
    model: str | None = None,
    swarm: str = "delivery",
    actor: str = "product-owner",
    workspace_factory: Callable[..., AgoraWorkspace] = AgoraWorkspace,
    runtime_discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
    preflight: Callable[..., StartPreparationResult] = ensure_start_ready,
    isolation: Callable[[Path, int], tuple[Path, str | None]] = isolate_dirty_work,
    executor_launcher: Callable[..., InceptionExecutionResult] = launch_inception_executor,
    inception_materializer: Callable[..., object] = materialize_deterministic_inception,
    deterministic_clarifier: Callable[..., object] = record_zero_question_clarification,
    launch_executor: bool = True,
    progress: Callable[[str], None] | None = None,
) -> StartFlowResult:
    """Read one issue through Core, persist a draft Intent, and stop for human review."""

    def notify(code: str) -> None:
        if progress is not None:
            try:
                progress(code)
            except OSError:
                pass  # Human presentation cannot invalidate an already performed Core operation.

    notify("start.inspect")
    root, isolation_action = isolation(root, issue)
    notify("start.workspace-ready")
    project = project or infer_project(root)
    runtime = _select_runtime(root, agent, discovery=runtime_discovery)
    if model and runtime.id != "opencode":
        raise StartFlowError("Explicit --model selection is currently supported only with --agent opencode")
    notify("start.runtime-ready")
    prepared = preflight(
        root,
        runtime,
        swarm_id=swarm,
        issue=issue,
        workspace_factory=workspace_factory,
    )
    root = prepared.root
    notify("start.project-ready")
    workspace = workspace_factory(cwd=root)
    preflight_actions = list(prepared.actions)
    resolved_swarm = prepared.swarm_id or swarm

    issue_url = f"https://github.com/{project}/issues/{issue}"
    work_record = _ensure_issue_work(
        workspace,
        root,
        swarm=resolved_swarm,
        actor=actor,
        issue=issue,
        issue_url=issue_url,
    )
    notify("start.work-ready")
    resolved_branch = getattr(work_record, "branch", None)
    if not resolved_branch and _is_git_repository(root):
        observed_branch = _run_git(root, "branch", "--show-current")
        resolved_branch = observed_branch or None
    run_id = f"ai-dlc-start-issue-{issue}"

    try:
        inspection = workspace.show_tool_run(run_id)
        if inspection.result is None or inspection.result.status != "completed":
            raise StartFlowError(f"Existing governed issue read {run_id} is not completed")
        notify("start.issue-reused")
    except FileNotFoundError:
        adapter = root / ".agora" / "tools" / "github-issues" / "TOOL.md"
        if not adapter.is_file():
            try:
                workspace.install_tool_adapter(
                    InstallToolAdapterInput(
                        adapter_id="github-issues",
                        scope="project",
                    )
                )
            except (FileNotFoundError, OSError, ValueError) as error:
                raise StartFlowError("GitHub issue adapter is unavailable") from error
        _ensure_issue_read_capability(workspace, root)
        notify("start.issue-read")
        try:
            workspace.invoke_tool(
                InvokeToolInput(
                    id=run_id,
                    tool_id="github-issues",
                    operation_id="view",
                    actor_id=actor,
                    swarm_id=resolved_swarm,
                    inputs={"issue": issue_url},
                    launch=True,
                )
            )
        except ValueError as error:
            diagnostic = _diagnose_issue_read_markdown(root, run_id)
            if diagnostic is not None:
                raise StartFlowError(f"Governed issue read is blocked by invalid Markdown at {diagnostic}") from error
            raise

    payload = _issue_payload(workspace, run_id)
    number = int(payload.get("number") or issue)
    title = str(payload.get("title") or "").strip()
    if not title:
        raise StartFlowError("GitHub issue has no title")

    intent_id = f"issue-{number}"
    try:
        existing = _get_target_intent(workspace, root, intent_id)
    except FileNotFoundError:
        existing = None
    except ValueError as error:
        target = root / ".agora" / "intents" / intent_id / "INTENT.md"
        try:
            read_markdown(target)
        except (OSError, ValueError) as detail:
            raise StartFlowError(
                f"Target Intent {intent_id} is invalid at {target.relative_to(root)}: {detail}"
            ) from error
        raise
    if existing is None:
        intent = workspace.create_intent(
            CreateIntentInput(
                id=intent_id,
                author=f"project:{actor}",
                problem=title,
                outcome=f"Deliver the outcome described by GitHub issue #{number}: {title}",
                affected_systems=[project],
                constraints=[],
                open_questions=[],
                source=issue_url,
            )
        )
    else:
        intent = existing

    notify("start.intent-ready")
    pathway = _select_pathway(root, payload)
    notify("start.pathway")
    deterministic = build_deterministic_inception(
        root,
        payload,
        intent_id=intent.id,
        work_id=work_record.id,
        pathway=pathway,
    )
    deterministic_relative = Path(deterministic.path).relative_to(root.resolve()).as_posix()
    notify("start.handoff")
    handoff = write_inception_handoff(
        root,
        intent_id=intent.id,
        issue_url=issue_url,
        issue_title=title,
        runtime_id=runtime.id,
        runtime_name=runtime.name,
        swarm_id=resolved_swarm,
        work_id=work_record.id,
        branch=resolved_branch,
        base_branch=getattr(work_record, "base_branch", None),
        pathway=pathway,
        deterministic_draft=deterministic_relative,
        semantic_gaps=deterministic.semantic_gaps,
    )

    materialization_actions: tuple[str, ...] = ()
    clarification_actions: tuple[str, ...] = ()
    if launch_executor and not deterministic.requires_llm:
        materialized = inception_materializer(
            root,
            workspace=workspace,
            swarm_id=resolved_swarm,
            work_id=work_record.id,
            intent_path=intent.path,
            issue=deterministic.issue,
            pathway=pathway,
        )
        materialization_actions = tuple(getattr(materialized, "actions", ()) or ())
        if not deterministic.semantic_gaps:
            clarification = deterministic_clarifier(
                workspace=workspace,
                swarm_id=swarm,
                work_id=work_record.id,
                actor_id=str(getattr(materialized, "actor_id", "") or ""),
            )
            clarification_actions = tuple(getattr(clarification, "actions", ()) or ())

    execution: InceptionExecutionResult | None = None
    inception_output: str | None = None
    inception_mode = "prepared"
    status = "inception-prepared"
    if launch_executor and not deterministic.requires_llm:
        notify("start.deterministic-inception")
        inception_output = deterministic.output
        inception_mode = "deterministic"
        notify("start.deterministic-complete")
        status = "human-review-required"
    elif launch_executor:
        notify("start.executor-launch")
        try:
            execution = executor_launcher(
                root,
                runtime=runtime,
                handoff_path=Path(handoff.path),
                swarm_id=swarm,
                work_id=work_record.id,
                responsible_actor=actor,
                model=model,
                workspace_factory=workspace_factory,
            )
        except ExecutorLaunchError as error:
            raise StartExecutorError(
                str(error),
                runtime_id=runtime.id,
                workspace_root=str(root),
                recoverable=error.recoverable,
            ) from error
        notify("start.executor-complete")
        inception_output = execution.output
        inception_mode = "llm"
        status = "human-review-required"
    else:
        notify("start.executor-skipped-launch")
        notify("start.executor-skipped-complete")

    notify("start.prepared")
    return StartFlowResult(
        project=project,
        issue=number,
        swarm_id=resolved_swarm,
        issue_url=issue_url,
        issue_title=title,
        intent_id=intent.id,
        intent_path=intent.path,
        work_id=work_record.id,
        work_path=work_record.path,
        base_branch=getattr(work_record, "base_branch", None),
        branch=resolved_branch,
        pathway=pathway,
        runtime_id=runtime.id,
        runtime_name=runtime.name,
        runtime_model=model,
        tool_run_id=run_id,
        handoff_path=handoff.path,
        skill_path=handoff.skill,
        workspace_root=str(root),
        workspace_isolated=isolation_action is not None,
        preflight_actions=tuple(
            ([isolation_action] if isolation_action is not None else [])
            + preflight_actions
            + list(materialization_actions)
            + list(clarification_actions)
        ),
        executor_session_id=execution.session_id if execution is not None else None,
        executor_result_path=execution.result_path if execution is not None else None,
        executor_summary_path=execution.summary_path if execution is not None else None,
        executor_output=execution.output if execution is not None else None,
        executor_reused=execution.reused if execution is not None else False,
        inception_mode=inception_mode,
        inception_output=inception_output,
        deterministic_inception_path=deterministic.path,
        semantic_gaps=deterministic.semantic_gaps,
        status=status,
    )


def render_start(result: StartFlowResult, *, lang: str = "en", details: bool = False) -> str:
    """Render the human Start outcome after automatic Inception execution when enabled."""

    branch = result.branch or t("guided.unknown", lang=lang)
    lines = [
        t("start.title", lang=lang),
        "",
        f"Issue #{result.issue} · {result.issue_title}",
        f"✓ {t('start.project', lang=lang)}: {result.project}",
        f"✓ {t('start.work', lang=lang)}: {result.work_id} · {branch}",
        (
            f"✓ {t('start.inception_engine', lang=lang)}: {t('start.deterministic_engine', lang=lang)}"
            if result.inception_mode == "deterministic"
            else f"✓ {t('start.selected_ai', lang=lang)}: {result.runtime_name}"
        ),
        f"✓ {t('start.pathway', lang=lang)}: {result.pathway}",
    ]
    if result.workspace_isolated:
        lines.append(f"✓ {t('start.workspace_ready', lang=lang)}")
    if result.preflight_actions:
        count = len(result.preflight_actions)
        key = "start.auto_prepared_one" if count == 1 else "start.auto_prepared_many"
        lines.append(t(key, lang=lang, count=count))

    if result.inception_output is not None:
        if result.inception_mode == "deterministic":
            lines.append(f"✓ {t('start.deterministic_completed', lang=lang)}")
        else:
            executor_state = (
                t("start.executor_reused", lang=lang)
                if result.executor_reused
                else t("start.executor_completed", lang=lang)
            )
            lines.append(f"✓ {result.runtime_name}: {executor_state}")
        lines.extend(
            [
                "",
                t("start.proposal_ready", lang=lang),
                "",
                result.inception_output or t("start.proposal_unavailable", lang=lang),
                "",
                t("start.human_decision_required", lang=lang),
                f"  {t('start.boundary1', lang=lang)}",
                f"  {t('start.boundary2', lang=lang)}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                t("start.inception_ready", lang=lang),
                f"  {t('start.inception_summary', lang=lang)}",
                "",
                t("start.next_executor", lang=lang),
                f"  {t('start.launch_executor', lang=lang, runtime=result.runtime_name)}",
                f"  {t('start.no_prompt', lang=lang)}",
            ]
        )

    if details:
        lines.extend(
            [
                "",
                t("start.details", lang=lang),
                f"  {t('start.workspace', lang=lang)}: {result.workspace_root}",
                f"  {t('start.governed_issue_read', lang=lang)}: {result.tool_run_id}",
                f"  {t('start.durable_intent', lang=lang)}: {result.intent_path}",
                f"  {t('start.portable_handoff', lang=lang)}: {result.handoff_path}",
                f"  {t('start.guided_skill', lang=lang)}: {result.skill_path}",
                f"  {t('start.base_branch', lang=lang)}: {result.base_branch or t('guided.unknown', lang=lang)}",
                f"  {t('start.deterministic_path', lang=lang)}: {result.deterministic_inception_path}",
                f"  {t('start.semantic_gaps', lang=lang)}: {', '.join(result.semantic_gaps) or '—'}",
            ]
        )
        if result.executor_session_id is not None:
            lines.extend(
                [
                    f"  {t('start.executor_session', lang=lang)}: {result.executor_session_id}",
                    f"  {t('start.executor_result', lang=lang)}: {result.executor_result_path}",
                    f"  {t('start.executor_summary', lang=lang)}: {result.executor_summary_path}",
                ]
            )

    lines.extend(["", f"{t('start.status', lang=lang)}: {result.status}"])
    return "\n".join(lines)
