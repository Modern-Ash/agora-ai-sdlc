"""Governed Git delivery for Pull Request delivery targets.

Agora Flow owns staging, commit, push and Pull Request creation. The user confirms
one Flow action; Git and GitHub remain implementation details. Only Work-owned
changes are staged, and merge authority is deliberately excluded.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml
from agora.model import AddEvidenceInput, InstallToolAdapterInput, InvokeToolInput, WorkActorInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.guided import GuidedDecision

_PR_URL = re.compile(r"https://github\.com/[^\s]+/pull/\d+")


@dataclass(frozen=True)
class PullRequestSubmission:
    branch: str
    base_branch: str
    commit_sha: str
    pull_request_url: str
    staged_paths: tuple[str, ...]


class DeliverySubmissionError(ValueError):
    """A governed Pull Request delivery could not be completed safely."""


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise DeliverySubmissionError((result.stderr or result.stdout or "git command failed").strip())
    return result


def _github_project(root: Path) -> str:
    remote = _git(root, "remote", "get-url", "origin").stdout.strip()
    patterns = (
        re.compile(r"^git@github\.com:(?P<project>[^/]+/[^/]+?)(?:\.git)?$"),
        re.compile(r"^https://github\.com/(?P<project>[^/]+/[^/]+?)(?:\.git)?/?$"),
        re.compile(r"^ssh://git@github\.com/(?P<project>[^/]+/[^/]+?)(?:\.git)?/?$"),
    )
    for pattern in patterns:
        match = pattern.match(remote)
        if match:
            return match.group("project").removesuffix(".git")
    raise DeliverySubmissionError("Pull Request delivery requires a GitHub origin remote")


def pull_request_delivery_enabled(root: Path) -> bool:
    config = root / "ai-sdlc" / "project.yaml"
    if config.is_file():
        try:
            payload = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            payload = {}
        target = payload.get("delivery_target")
        if isinstance(target, dict):
            value = str(target.get("type") or "").strip().casefold()
            if value:
                return value == "pull-request"
        elif isinstance(target, str) and target.strip():
            return target.strip().casefold() == "pull-request"
    try:
        _github_project(root)
    except (OSError, DeliverySubmissionError):
        return False
    return True


def _work_owned(path: str, work: str) -> bool:
    normalized = path.replace("\\", "/")
    if not normalized.startswith(".agora/"):
        return normalized != "ai-sdlc/project.yaml"
    prefixes = (
        f".agora/intents/{work}/",
        f".agora/ai-sdlc/handoffs/{work}/",
        f".agora/ai-sdlc/verification/{work}/",
        f".agora/ai-sdlc/wizard/{work}/",
    )
    return normalized.startswith(prefixes) or f"/work/{work}/" in normalized


def work_change_set(root: Path, work: str) -> tuple[str, ...]:
    tracked = _git(root, "diff", "--name-only", "HEAD", "--").stdout.splitlines()
    staged = _git(root, "diff", "--cached", "--name-only", "--").stdout.splitlines()
    untracked = _git(root, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
    values = []
    for path in (*tracked, *staged, *untracked):
        value = path.strip()
        if value and value not in values and _work_owned(value, work):
            values.append(value)
    return tuple(values)


def _existing_pr(root: Path, branch: str, base: str) -> str | None:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--base",
            base,
            "--state",
            "all",
            "--limit",
            "1",
            "--json",
            "url",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list) or not payload:
        return None
    url = payload[0].get("url") if isinstance(payload[0], dict) else None
    return str(url) if url else None


def _ensure_pr_adapter(workspace: AgoraWorkspace, root: Path) -> None:
    manifest = root / ".agora" / "tools" / "github-pull-requests" / "TOOL.md"
    if manifest.is_file():
        return
    workspace.install_tool_adapter(
        InstallToolAdapterInput(
            adapter_id="github-pull-requests",
            scope="project",
        )
    )


def _commit_if_needed(
    workspace: AgoraWorkspace,
    root: Path,
    decision: GuidedDecision,
    actor: str,
    paths: tuple[str, ...],
) -> str:
    if paths:
        result = _git(root, "add", "--", *paths)
        if result.returncode != 0:
            raise DeliverySubmissionError("Could not stage the Work change set")

    staged = _git(root, "diff", "--cached", "--quiet", check=False)
    if staged.returncode not in {0, 1}:
        raise DeliverySubmissionError("Could not inspect the staged Work change set")

    if staged.returncode == 1:
        diff = _git(root, "diff", "--cached", "--binary").stdout
        digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()[:12]
        run_id = f"ai-sdlc-{decision.work}-commit-{digest}"
        workspace.invoke_tool(
            InvokeToolInput(
                id=run_id,
                tool_id="repository",
                operation_id="commit",
                actor_id=actor,
                swarm_id=decision.swarm,
                work_id=decision.work,
                inputs={"message": f"feat: deliver {decision.work}"},
                launch=True,
            )
        )
        inspection = workspace.show_tool_run(run_id)
        if inspection.result is None or inspection.result.status != "completed":
            raise DeliverySubmissionError("Governed repository commit failed")

    return _git(root, "rev-parse", "HEAD").stdout.strip()


def submit_pull_request(
    root: Path,
    decision: GuidedDecision,
    *,
    workspace_factory=AgoraWorkspace,
) -> PullRequestSubmission:
    root = root.resolve()
    workspace = workspace_factory(cwd=root)
    work_record = workspace.show_work(decision.swarm, decision.work)

    branch = str(getattr(work_record, "branch", None) or _git(root, "branch", "--show-current").stdout.strip())
    base = str(getattr(work_record, "base_branch", None) or "main")
    current = _git(root, "branch", "--show-current").stdout.strip()
    if not branch or current != branch:
        raise DeliverySubmissionError(
            f"Flow must submit the Work-owned branch {branch!r}; current branch is {current!r}"
        )

    actor = decision.developer_actor
    if not actor or decision.developer_actor_kind != "ai-agent":
        raise DeliverySubmissionError("Pull Request delivery requires the assigned developer actor")

    paths = work_change_set(root, decision.work)
    commit_sha = _commit_if_needed(workspace, root, decision, actor, paths)

    ahead = int((_git(root, "rev-list", "--count", f"{base}..HEAD").stdout.strip() or "0"))
    if ahead < 1:
        raise DeliverySubmissionError("There are no Work commits to submit as a Pull Request")

    push = _git(root, "push", "--set-upstream", "origin", branch, check=False)
    if push.returncode != 0:
        raise DeliverySubmissionError((push.stderr or push.stdout or "git push failed").strip())

    project = _github_project(root)
    existing = _existing_pr(root, branch, base)
    pr_url = existing

    _ensure_pr_adapter(workspace, root)
    if pr_url is None:
        run_id = f"ai-sdlc-{decision.work}-pull-request"
        workspace.invoke_tool(
            InvokeToolInput(
                id=run_id,
                tool_id="github-pull-requests",
                operation_id="create",
                actor_id=actor,
                swarm_id=decision.swarm,
                work_id=decision.work,
                inputs={
                    "project": project,
                    "base": base,
                    "head": branch,
                    "title": f"feat: deliver {decision.work}",
                    "description": (
                        f"Governed Agora AI-SDLC delivery for {decision.title or decision.work}.\n\n"
                        f"Work: {decision.swarm}/{decision.work}"
                    ),
                },
                launch=True,
            )
        )
        inspection = workspace.show_tool_run(run_id)
        if inspection.result is None or inspection.result.status != "completed":
            raise DeliverySubmissionError("Governed Pull Request creation failed")
        match = _PR_URL.search(inspection.result.stdout or "")
        if match is None:
            raise DeliverySubmissionError("Pull Request was created but its URL was not returned")
        pr_url = match.group(0)

    workspace.add_evidence(
        AddEvidenceInput(
            swarm_id=decision.swarm,
            work_id=decision.work,
            actor_id=actor,
            type="deployment",
            result="success",
            artifact_refs=[pr_url],
            tested_commit=commit_sha,
            environment="pull-request",
            dedupe_key=f"pull-request:{pr_url}",
        )
    )

    for criterion in decision.unsatisfied_criteria:
        statuses = dict(decision.criterion_statuses).get(criterion, ())
        if "verified" in statuses and "deployed" not in statuses:
            workspace.satisfy_criterion(
                WorkActorInput(
                    swarm_id=decision.swarm,
                    work_id=decision.work,
                    actor_id=actor,
                ),
                criterion,
                stage="deployed",
            )

    return PullRequestSubmission(
        branch=branch,
        base_branch=base,
        commit_sha=commit_sha,
        pull_request_url=pr_url,
        staged_paths=paths,
    )
