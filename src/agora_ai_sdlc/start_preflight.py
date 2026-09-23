"""Defensive, idempotent preparation for the zero-ceremony Start path.

This module performs only deterministic, non-destructive repairs. Ambiguous user
customizations fail closed instead of being overwritten.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml
from agora.markdown import MarkdownDocument, read_markdown, render_markdown
from agora.methods import load_method_contract
from agora.model import (
    AddActorInput,
    AssignActorInput,
    CreateSwarmInput,
    InitInput,
    InstallMethodInput,
    InstallToolAdapterInput,
)
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.profile_activation import adoption_profiles
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.skill_resources import install_resources, resource_root

METHOD_ID = "ai-sdlc"
METHOD_VERSION = "0.2.0"
DEFAULT_PROFILE = "starter"


class StartPreparationError(ValueError):
    """A safe automatic preparation step could not proceed unambiguously."""


@dataclass(frozen=True)
class StartPreparationResult:
    root: Path
    actions: tuple[str, ...]


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def is_git_work_tree(root: Path) -> bool:
    result = _run_git(root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def repository_root(root: Path) -> Path:
    candidate = root.expanduser().resolve()
    result = _run_git(candidate, "rev-parse", "--show-toplevel")
    if result.returncode != 0 or not result.stdout.strip():
        raise StartPreparationError(
            f"{candidate} is not inside a Git work tree. Run Start from an existing repository "
            "or pass --root <repository>."
        )
    return Path(result.stdout.strip()).resolve()


def _worktree_branch_map(root: Path) -> dict[str, Path]:
    result = _run_git(root, "worktree", "list", "--porcelain")
    if result.returncode != 0:
        return {}
    found: dict[str, Path] = {}
    path: Path | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            path = Path(line.removeprefix("worktree ").strip()).resolve()
        elif line.startswith("branch refs/heads/") and path is not None:
            found[line.removeprefix("branch refs/heads/").strip()] = path
    return found


def _default_base_branch(root: Path) -> str:
    result = _run_git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if result.returncode == 0 and result.stdout.strip().startswith("origin/"):
        return result.stdout.strip().removeprefix("origin/")
    for candidate in ("main", "master"):
        probe = _run_git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{candidate}")
        if probe.returncode == 0:
            return candidate
    current = _run_git(root, "branch", "--show-current")
    if current.returncode == 0 and current.stdout.strip():
        return current.stdout.strip()
    raise StartPreparationError("Cannot determine a safe base branch for this repository.")


def isolate_dirty_work(root: Path, issue: int) -> tuple[Path, str | None]:
    """Return an issue workspace without touching unrelated dirty work."""

    root = repository_root(root)
    desired = f"ai-sdlc/issue-{issue}"
    current = _run_git(root, "branch", "--show-current").stdout.strip()
    dirty = bool(_run_git(root, "status", "--porcelain").stdout.strip())
    if not dirty or current == desired:
        return root, None

    attached = _worktree_branch_map(root)
    if desired in attached:
        return attached[desired], "workspace.reused"

    base = _default_base_branch(root)
    parent = root.parent / f".{root.name}-agora-worktrees"
    target = parent / f"issue-{issue}"
    if target.exists():
        if is_git_work_tree(target):
            branch = _run_git(target, "branch", "--show-current").stdout.strip()
            if branch == desired:
                return target.resolve(), "workspace.reused"
        raise StartPreparationError(
            f"Automatic isolation is blocked because {target} already exists and is not the "
            f"workspace for {desired}. No files were changed there."
        )

    parent.mkdir(parents=True, exist_ok=True)
    local = _run_git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{desired}").returncode == 0
    remote = _run_git(root, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{desired}").returncode == 0
    if local:
        command = ["worktree", "add", str(target), desired]
    elif remote:
        command = ["worktree", "add", "-b", desired, str(target), f"origin/{desired}"]
    else:
        command = ["worktree", "add", "-b", desired, str(target), base]
    result = _run_git(root, *command)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "git worktree add failed").strip()
        raise StartPreparationError(f"Could not create an isolated issue workspace: {detail}")
    return target.resolve(), "workspace.created"


def _split_front_matter(text: str) -> tuple[dict, str] | None:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return None
    marker = normalized.find("\n---\n", 4)
    if marker < 0:
        return None
    front = normalized[4:marker]
    body = normalized[marker + 5 :]
    try:
        parsed = yaml.safe_load(front) or {}
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else {}, body


def _formatting_only_equivalent(installed: Path, packaged: Path) -> bool:
    installed_files = {
        path.relative_to(installed) for path in installed.rglob("*") if path.is_file() and not path.is_symlink()
    }
    packaged_files = {
        path.relative_to(packaged) for path in packaged.rglob("*") if path.is_file() and not path.is_symlink()
    }
    if installed_files != packaged_files:
        return False
    for relative in packaged_files:
        left = installed / relative
        right = packaged / relative
        if relative.suffix.lower() != ".md":
            if left.read_bytes() != right.read_bytes():
                return False
            continue
        left_parts = _split_front_matter(left.read_text(encoding="utf-8"))
        right_parts = _split_front_matter(right.read_text(encoding="utf-8"))
        if left_parts is None or right_parts is None:
            if left.read_text(encoding="utf-8") != right.read_text(encoding="utf-8"):
                return False
            continue
        left_front, left_body = left_parts
        right_front, right_body = right_parts
        if left_front != right_front or left_body.strip() != right_body.strip():
            return False
    return True


def _ensure_method(workspace: AgoraWorkspace, root: Path, actions: list[str]) -> None:
    target = root / ".agora" / "methods" / METHOD_ID
    source = asset_root("registry") / "method-versions" / METHOD_ID / METHOD_VERSION
    if not target.is_dir():
        workspace.install_method(InstallMethodInput(source=str(source), scope="project"))
        actions.append("method.installed")
        return
    try:
        load_method_contract(target)
        return
    except (OSError, ValueError) as error:
        if not _formatting_only_equivalent(target, source):
            raise StartPreparationError(
                "The installed AI-SDLC Method Pack is malformed and differs from the packaged "
                "version. Automatic repair was refused to preserve possible local customizations. "
                "Use aisdlc doctor for diagnostics."
            ) from error
    for packaged in source.rglob("*"):
        if not packaged.is_file():
            continue
        relative = packaged.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(packaged.read_bytes())
    load_method_contract(target)
    actions.append("method.repaired")


def _ensure_skill(root: Path, actions: list[str]) -> None:
    source = resource_root()
    destination = root / ".agora" / "skills" / "agora-ai-sdlc-guided"
    required = (
        Path("SKILL.md"),
        Path("references/inception.md"),
        Path("references/construction.md"),
        Path("references/review.md"),
        Path("references/delivery.md"),
        Path("references/readiness.md"),
        Path("references/governance.md"),
    )
    missing = [relative for relative in required if not (destination / relative).is_file()]
    if not missing:
        return
    for relative in required:
        existing = destination / relative
        packaged = source / relative
        if existing.is_file() and existing.read_text(encoding="utf-8") != packaged.read_text(encoding="utf-8"):
            raise StartPreparationError(
                "The guided AI-SDLC skill is incomplete and contains local changes. Automatic repair was refused."
            )
    install_resources(source, destination)
    actions.append("skill.installed")


def _ensure_project_selection(root: Path, actions: list[str]) -> None:
    project_file = root / ".agora" / "project.md"
    document = read_markdown(project_file)
    attributes = dict(document.attributes)
    flavor = attributes.get("active-flavor")
    if flavor not in {None, "", "none", METHOD_ID}:
        raise StartPreparationError(
            f"This project already selects active flavor {flavor!r}; Start will not replace it automatically."
        )
    changed = False
    if flavor != METHOD_ID:
        attributes["active-flavor"] = METHOD_ID
        changed = True
    if attributes.get("active-profile") in {None, "", "none"}:
        attributes["active-profile"] = DEFAULT_PROFILE
        changed = True
    if attributes.get("active-depth") in {None, "", "none"}:
        attributes["active-depth"] = adoption_profiles()[DEFAULT_PROFILE]
        changed = True
    if changed:
        project_file.write_text(
            render_markdown(MarkdownDocument(attributes=attributes, body=document.body)),
            encoding="utf-8",
        )
        actions.append("project.flavor-selected")


def _ensure_metadata(root: Path, runtime: RuntimeDiscovery, actions: list[str]) -> None:
    target = root / "ai-sdlc" / "project.yaml"
    if target.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "agora-ai-sdlc/project-config/v1",
        "project": {"id": root.name, "name": root.name, "mode": "existing"},
        "language": "unknown",
        "framework": None,
        "pathway": "brownfield",
        "integrations": ["github"],
        "profile": DEFAULT_PROFILE,
        "depth": adoption_profiles()[DEFAULT_PROFILE],
        "runtimes": [
            {
                "id": runtime.id,
                "integration": runtime.id if runtime.id in {"codex", "claude"} else "generic",
                "provider": runtime.id,
                "model": "configured-by-runtime",
            }
        ],
        "role_execution": {"developer": runtime.id},
        "method": {"id": METHOD_ID, "version": METHOD_VERSION},
    }
    target.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    actions.append("metadata.created")


def _ensure_actors(workspace: AgoraWorkspace, runtime: RuntimeDiscovery, actions: list[str]) -> str:
    actors = {item.id for item in workspace.list_actors()}
    if "product-owner" not in actors:
        workspace.add_actor(
            AddActorInput(
                id="product-owner",
                name="Product Owner",
                kind="human",
                capabilities=["specification"],
                scope="project",
            )
        )
        actions.append("actor.product-owner-created")
    runtime_actor = f"ai-{runtime.id}"
    if runtime_actor not in actors:
        integration = runtime.id if runtime.id in {"codex", "claude"} else "generic"
        workspace.add_actor(
            AddActorInput(
                id=runtime_actor,
                name=runtime.name,
                kind="ai-agent",
                capabilities=["specification", "implementation", "operations"],
                scope="project",
                integration=integration,
                provider=runtime.id,
                model="configured-by-runtime",
            )
        )
        actions.append("actor.runtime-created")
    return runtime_actor


def _ensure_delivery_swarm(
    workspace: AgoraWorkspace,
    root: Path,
    runtime_actor: str,
    swarm_id: str,
    actions: list[str],
) -> None:
    try:
        swarm = workspace.show_swarm(swarm_id)
    except FileNotFoundError:
        swarm = workspace.create_swarm(
            CreateSwarmInput(
                id=swarm_id,
                objective=f"Deliver {root.name}",
                method=METHOD_ID,
                create_branch=False,
            )
        )
        actions.append("swarm.created")
    if swarm.method != METHOD_ID:
        raise StartPreparationError(
            f"Swarm {swarm_id!r} uses method {swarm.method!r}; Start will not silently replace its governance method."
        )
    assignments = dict(workspace.show_swarm(swarm_id).assignments)
    if "product-owner" not in assignments:
        workspace.assign_actor(AssignActorInput(swarm_id=swarm_id, role_id="product-owner", actor_id="product-owner"))
        actions.append("swarm.product-owner-assigned")
    assignments = dict(workspace.show_swarm(swarm_id).assignments)
    if "developer" not in assignments:
        workspace.assign_actor(AssignActorInput(swarm_id=swarm_id, role_id="developer", actor_id=runtime_actor))
        actions.append("swarm.developer-assigned")


def ensure_start_ready(
    root: Path,
    runtime: RuntimeDiscovery,
    *,
    swarm_id: str = "delivery",
    workspace_factory=AgoraWorkspace,
) -> StartPreparationResult:
    """Prepare the minimum safe AI-SDLC project state required by Start."""

    root = repository_root(root)
    actions: list[str] = []
    project_file = root / ".agora" / "project.md"
    workspace = workspace_factory(cwd=root)
    if not project_file.is_file():
        init_kwargs = {
            "integration": "generic",
            "provider": "local",
            "model": "human",
            "default_method": "scrum",
        }
        fields = getattr(InitInput, "__dataclass_fields__", {})
        if "active_flavor" in fields:
            init_kwargs.update(
                active_flavor=METHOD_ID,
                active_profile=DEFAULT_PROFILE,
                active_depth=adoption_profiles()[DEFAULT_PROFILE],
            )
        workspace.initialize(InitInput(**init_kwargs))
        actions.append("project.initialized")

    _ensure_project_selection(root, actions)
    _ensure_method(workspace, root, actions)
    _ensure_skill(root, actions)

    adapter = root / ".agora" / "tools" / "github-issues" / "TOOL.md"
    if not adapter.is_file():
        workspace.install_tool_adapter(InstallToolAdapterInput(adapter_id="github-issues", scope="project"))
        actions.append("github-adapter.installed")

    runtime_actor = _ensure_actors(workspace, runtime, actions)
    _ensure_delivery_swarm(workspace, root, runtime_actor, swarm_id, actions)
    _ensure_metadata(root, runtime, actions)

    return StartPreparationResult(root=root, actions=tuple(actions))
