"""AI-SDLC aligned entry flow for starting real delivery work from an issue."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from agora.model import (
    CreateIntentInput,
    CreateWorkInput,
    InstallMethodInput,
    InstallToolAdapterInput,
    InvokeToolInput,
)
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.i18n import t
from agora_ai_sdlc.inception_handoff import write_inception_handoff
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.start_preflight import (
    StartPreparationResult,
    ensure_start_ready,
    isolate_dirty_work,
)


class StartFlowError(ValueError):
    """Raised when the governed start flow cannot be prepared safely."""


@dataclass(frozen=True)
class StartFlowResult:
    project: str
    issue: int
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
    tool_run_id: str
    handoff_path: str
    skill_path: str
    workspace_root: str
    workspace_isolated: bool
    preflight_actions: tuple[str, ...]
    status: str = "human-review-required"

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
                return item
        raise StartFlowError(f"Requested AI runtime {requested!r} is not installed and responsive")
    configured = [item for item in available if item.configured]
    if configured:
        return configured[0]
    if available:
        return available[0]
    raise StartFlowError("No responsive AI CLI runtime was detected")


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
    swarm: str = "delivery",
    actor: str = "product-owner",
    workspace_factory: Callable[..., AgoraWorkspace] = AgoraWorkspace,
    runtime_discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
    preflight: Callable[..., StartPreparationResult] = ensure_start_ready,
    isolation: Callable[[Path, int], tuple[Path, str | None]] = isolate_dirty_work,
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
    notify("start.runtime-ready")
    prepared = preflight(
        root,
        runtime,
        swarm_id=swarm,
        workspace_factory=workspace_factory,
    )
    root = prepared.root
    notify("start.project-ready")
    workspace = workspace_factory(cwd=root)

    issue_url = f"https://github.com/{project}/issues/{issue}"
    work_record = _ensure_issue_work(
        workspace,
        root,
        swarm=swarm,
        actor=actor,
        issue=issue,
        issue_url=issue_url,
    )
    notify("start.work-ready")
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
        workspace.invoke_tool(
            InvokeToolInput(
                id=run_id,
                tool_id="github-issues",
                operation_id="view",
                actor_id=actor,
                swarm_id=swarm,
                inputs={"issue": issue_url},
                launch=True,
            )
        )

    payload = _issue_payload(workspace, run_id)
    number = int(payload.get("number") or issue)
    title = str(payload.get("title") or "").strip()
    if not title:
        raise StartFlowError("GitHub issue has no title")

    intent_id = f"issue-{number}"
    existing = next((item for item in workspace.list_intents() if item.id == intent_id), None)
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
    notify("start.handoff")
    handoff = write_inception_handoff(
        root,
        intent_id=intent.id,
        issue_url=issue_url,
        issue_title=title,
        runtime_id=runtime.id,
        runtime_name=runtime.name,
        swarm_id=swarm,
        work_id=work_record.id,
        branch=getattr(work_record, "branch", None),
        base_branch=getattr(work_record, "base_branch", None),
        pathway=pathway,
    )

    notify("start.prepared")
    return StartFlowResult(
        project=project,
        issue=number,
        issue_url=issue_url,
        issue_title=title,
        intent_id=intent.id,
        intent_path=intent.path,
        work_id=work_record.id,
        work_path=work_record.path,
        base_branch=getattr(work_record, "base_branch", None),
        branch=getattr(work_record, "branch", None),
        pathway=pathway,
        runtime_id=runtime.id,
        runtime_name=runtime.name,
        tool_run_id=run_id,
        handoff_path=handoff.path,
        skill_path=handoff.skill,
        workspace_root=str(root),
        workspace_isolated=isolation_action is not None,
        preflight_actions=tuple(
            ([isolation_action] if isolation_action is not None else []) + list(prepared.actions)
        ),
    )


def render_start(result: StartFlowResult, *, lang: str = "en") -> str:
    """Render the localized AI-led handoff without changing persisted semantics."""

    return "\n".join(
        [
            t("start.title", lang=lang),
            "",
            f"Issue: #{result.issue} {result.issue_title}",
            f"{t('start.project', lang=lang)}: {result.project}",
            *(
                [f"{t('start.workspace', lang=lang)}: {result.workspace_root}"]
                if result.workspace_isolated
                else []
            ),
            *(
                [t("start.auto_prepared", lang=lang, count=len(result.preflight_actions))]
                if result.preflight_actions
                else []
            ),
            f"{t('start.candidate_intent', lang=lang)}: {result.intent_id} ({t('common.draft', lang=lang)})",
            f"{t('start.work', lang=lang)}: {result.work_id}",
            f"{t('start.branch', lang=lang)}: {result.branch or 'unknown'}"
            + (f" ({t('start.base_branch', lang=lang)}: {result.base_branch})" if result.base_branch else ""),
            f"{t('start.pathway', lang=lang)}: {result.pathway}",
            f"{t('start.selected_ai', lang=lang)}: {result.runtime_name}",
            "",
            t("start.ai_next_move", lang=lang),
            f"  1. {t('start.step1', lang=lang)}",
            f"  2. {t('start.step2', lang=lang)}",
            f"  3. {t('start.step3', lang=lang)}",
            f"  4. {t('start.step4', lang=lang)}",
            "",
            t("start.human_boundary", lang=lang),
            f"  {t('start.boundary1', lang=lang)}",
            f"  {t('start.boundary2', lang=lang)}",
            "",
            f"{t('start.governed_issue_read', lang=lang)}: {result.tool_run_id}",
            f"{t('start.durable_intent', lang=lang)}: {result.intent_path}",
            f"{t('start.portable_handoff', lang=lang)}: {result.handoff_path}",
            f"{t('start.guided_skill', lang=lang)}: {result.skill_path}",
            "",
            t("start.next_executor", lang=lang),
            f"  {t('start.launch_executor', lang=lang, runtime=result.runtime_name)}",
            f"  {t('start.no_prompt', lang=lang)}",
            "",
            f"{t('start.status', lang=lang)}: {result.status}",
        ]
    )
