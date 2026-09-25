"""Defensive, idempotent preparation for the zero-ceremony Start path.

This module performs only deterministic, non-destructive repairs. Ambiguous user
customizations fail closed instead of being overwritten.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml
from agora.filesystem import packs_root
from agora.markdown import MarkdownDocument, parse_markdown, read_markdown, render_markdown
from agora.methods import load_method_contract
from agora.model import (
    AddActorInput,
    AssignActorInput,
    CreateSwarmInput,
    InitInput,
    InstallMethodInput,
    InstallToolAdapterInput,
    RefreshPackLockInput,
)
from agora.tools import load_tool_contract
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


def _repair_core_front_matter(root: Path, actions: list[str]) -> bool:
    """Canonicalize semantically valid Agora front matter that external formatters wrapped.

    Returns whether a pack tree or its composition lock changed, so the caller can
    refresh the deterministic pack inventory after a semantics-preserving repair.
    """

    state = root / ".agora"
    if not state.is_dir():
        return False
    repaired = 0
    pack_state_changed = False
    for path in sorted(state.rglob("*.md")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            read_markdown(path)
            continue
        except (OSError, ValueError):
            pass

        try:
            original = path.read_text(encoding="utf-8")
        except OSError:
            continue
        parts = _split_front_matter(original)
        if parts is None:
            continue
        attributes, body = parts
        schema = attributes.get("schema")
        if not isinstance(schema, str) or not schema.startswith(("agora/", "agora-ai-sdlc/")):
            continue
        try:
            json.dumps(attributes)
            canonical = render_markdown(MarkdownDocument(attributes=attributes, body=body))
            parse_markdown(canonical)
        except (TypeError, ValueError):
            continue
        path.write_text(canonical, encoding="utf-8")
        repaired += 1
        relative = path.relative_to(state)
        if relative == Path("PACKS.lock.md") or relative.parts[:1] in {("methods",), ("tools",)}:
            pack_state_changed = True

    if repaired:
        actions.append(f"state.front-matter-repaired:{repaired}")
    return pack_state_changed


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


def _body_only_equivalent(installed: Path, packaged: Path) -> bool:
    if installed.read_bytes() == packaged.read_bytes():
        return True
    packaged_parts = _split_front_matter(packaged.read_text(encoding="utf-8"))
    if packaged_parts is None:
        return False
    packaged_front, packaged_body = packaged_parts
    installed_text = installed.read_text(encoding="utf-8")
    installed_parts = _split_front_matter(installed_text)
    if installed_parts is not None:
        installed_front, installed_body = installed_parts
        return installed_front == packaged_front and installed_body.strip() == packaged_body.strip()
    return installed_text.strip() == packaged_body.strip()


def _repair_bundled_adapter(target: Path, source: Path) -> bool:
    source_files = {
        path.relative_to(source): path for path in source.rglob("*") if path.is_file() and not path.is_symlink()
    }
    target_files = {
        path.relative_to(target): path for path in target.rglob("*") if path.is_file() and not path.is_symlink()
    }

    extra = sorted(set(target_files) - set(source_files))
    if extra:
        return False

    for relative, packaged in source_files.items():
        installed = target_files.get(relative)
        if installed is None:
            continue
        if not _body_only_equivalent(installed, packaged):
            return False

    for relative, packaged in source_files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(packaged.read_bytes())
    return True


def _ensure_github_adapter(workspace: AgoraWorkspace, root: Path, actions: list[str]) -> None:
    target = root / ".agora" / "tools" / "github-issues"
    source = packs_root() / "adapters" / "cli" / "github-issues"

    if not (target / "TOOL.md").is_file():
        workspace.install_tool_adapter(InstallToolAdapterInput(adapter_id="github-issues", scope="project"))
        actions.append("github-adapter.installed")
        return

    try:
        contract = load_tool_contract(target)
        if "view" not in contract.operations:
            raise ValueError("github-issues adapter is missing the view operation")
        return
    except (OSError, ValueError) as error:
        if not source.is_dir() or not _repair_bundled_adapter(target, source):
            raise StartPreparationError(
                "The installed GitHub Issues adapter is malformed or customized. "
                "Automatic repair was refused to preserve local changes. "
                "Inspect .agora/tools/github-issues or run aisdlc doctor."
            ) from error

    load_tool_contract(target)
    workspace.refresh_pack_lock(RefreshPackLockInput(scope="project"))
    actions.append("github-adapter.repaired")
    actions.append("pack-lock.refreshed")


def _ensure_github_pr_adapter(workspace: AgoraWorkspace, root: Path, actions: list[str]) -> None:
    target = root / ".agora" / "tools" / "github-pull-requests"
    if (target / "TOOL.md").is_file():
        try:
            contract = load_tool_contract(target)
            if "create" in contract.operations:
                return
        except (OSError, ValueError):
            pass

    workspace.install_tool_adapter(
        InstallToolAdapterInput(
            adapter_id="github-pull-requests",
            scope="project",
        )
    )
    workspace.refresh_pack_lock(RefreshPackLockInput(scope="project"))
    actions.append("github-pr-adapter.installed")
    actions.append("pack-lock.refreshed")


def _ensure_review_write_capability(workspace: AgoraWorkspace, root: Path, actions: list[str]) -> None:
    role = root / ".agora" / "methods" / METHOD_ID / "roles" / "developer.md"
    if not role.is_file():
        return
    content = role.read_text(encoding="utf-8")
    if '"review.write"' in content:
        return

    source = asset_root("registry") / "method-versions" / METHOD_ID / METHOD_VERSION
    packaged = source / "roles" / "developer.md"
    if not packaged.is_file() or '"review.write"' not in packaged.read_text(encoding="utf-8"):
        raise StartPreparationError("Packaged AI-SDLC Developer role cannot create Pull Requests")
    workspace.install_method(
        InstallMethodInput(
            source=str(source),
            scope="project",
            force=True,
        )
    )
    actions.append("method.developer-review-write-repaired")


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

    pack_state_repaired = _repair_core_front_matter(root, actions)
    _ensure_project_selection(root, actions)
    _ensure_method(workspace, root, actions)
    _ensure_review_write_capability(workspace, root, actions)
    if pack_state_repaired:
        workspace.refresh_pack_lock(RefreshPackLockInput(scope="project"))
        actions.append("pack-lock.refreshed")
    _ensure_skill(root, actions)

    _ensure_github_adapter(workspace, root, actions)
    _ensure_github_pr_adapter(workspace, root, actions)

    runtime_actor = _ensure_actors(workspace, runtime, actions)
    _ensure_delivery_swarm(workspace, root, runtime_actor, swarm_id, actions)
    _ensure_metadata(root, runtime, actions)

    return StartPreparationResult(root=root, actions=tuple(actions))
