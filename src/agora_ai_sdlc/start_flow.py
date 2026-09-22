"""AI-SDLC aligned entry flow for starting real delivery work from an issue."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from agora.model import CreateIntentInput, InstallToolAdapterInput, InvokeToolInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.i18n import t
from agora_ai_sdlc.inception_handoff import write_inception_handoff
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes


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
    runtime_id: str
    runtime_name: str
    tool_run_id: str
    handoff_path: str
    skill_path: str
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
    root = root.expanduser().resolve()
    project = project or infer_project(root)
    runtime = _select_runtime(root, agent, discovery=runtime_discovery)
    notify("start.runtime-ready")
    workspace = workspace_factory(cwd=root)

    issue_url = f"https://github.com/{project}/issues/{issue}"
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
    notify("start.handoff")
    handoff = write_inception_handoff(
        root,
        intent_id=intent.id,
        issue_url=issue_url,
        issue_title=title,
        runtime_id=runtime.id,
        runtime_name=runtime.name,
    )

    notify("start.prepared")
    return StartFlowResult(
        project=project,
        issue=number,
        issue_url=issue_url,
        issue_title=title,
        intent_id=intent.id,
        intent_path=intent.path,
        runtime_id=runtime.id,
        runtime_name=runtime.name,
        tool_run_id=run_id,
        handoff_path=handoff.path,
        skill_path=handoff.skill,
    )


def render_start(result: StartFlowResult, *, lang: str = "en") -> str:
    """Render the localized AI-led handoff without changing persisted semantics."""

    return "\n".join(
        [
            t("start.title", lang=lang),
            "",
            f"Issue: #{result.issue} {result.issue_title}",
            f"{t('start.project', lang=lang)}: {result.project}",
            f"{t('start.candidate_intent', lang=lang)}: {result.intent_id} ({t('common.draft', lang=lang)})",
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
