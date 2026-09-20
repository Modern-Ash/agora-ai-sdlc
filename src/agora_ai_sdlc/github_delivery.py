"""GitHub delivery profile over Agora Core's reviewed CLI Tool Packs."""

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

import yaml
from agora.markdown import read_markdown, render_markdown
from agora.model import InstallToolAdapterInput, RefreshPackLockInput

from agora_ai_sdlc.depth_profiles import asset_root

SCHEMA = "agora-ai-sdlc/integration-profile/v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
SUCCESS = {"success", "successful", "pass", "passed"}


class GitHubDeliveryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def load_profile() -> dict:
    path = asset_root("profiles") / "integrations" / "github" / "profile.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("id") != "github-delivery":
        raise GitHubDeliveryError("github.profile.invalid", "invalid GitHub delivery profile")
    if data.get("default_mode") != "read-only":
        raise GitHubDeliveryError("github.profile.default", "GitHub delivery must default to read-only")
    return data


def install_read_only(workspace, project_root: Path) -> tuple[str, ...]:
    """Install reviewed adapters and only the profile's declared read grants."""
    profile = load_profile()
    for adapter in profile["adapters"]:
        workspace.install_tool_adapter(InstallToolAdapterInput(adapter_id=adapter, scope="project"))
    method = project_root / ".agora" / "methods" / "ai-sdlc"
    for role, grants in profile["read_roles"].items():
        path = method / "roles" / f"{role}.md"
        document = read_markdown(path)
        capabilities = document.attributes["allowed-tool-capabilities"]
        for capability in grants:
            if capability not in capabilities:
                capabilities.append(capability)
        path.write_text(render_markdown(document), encoding="utf-8")
    workspace.refresh_pack_lock(RefreshPackLockInput(scope="project"))
    return tuple(profile["adapters"])


def authorize_operation(
    operation: str,
    *,
    mode: str | None = None,
    granted_capabilities: Iterable[str] = (),
    confirmed: bool = False,
) -> dict:
    """Evaluate flavor policy before Core prepares or launches an adapter operation."""
    profile = load_profile()
    selected_mode = mode or profile["default_mode"]
    if selected_mode not in profile["modes"]:
        raise GitHubDeliveryError("github.mode.unknown", f"unknown permission mode {selected_mode!r}")
    if operation not in profile["operations"]:
        raise GitHubDeliveryError("github.operation.unknown", f"unknown operation {operation!r}")
    contract = profile["operations"][operation]
    capability = contract["capability"]
    policy_capabilities = set(profile["modes"][selected_mode]["capabilities"])
    blockers = []
    if capability not in policy_capabilities:
        blockers.append({"code": "github.mode.denied", "message": f"{selected_mode} does not permit {capability}"})
    if contract["risk"] != "read" and capability not in set(granted_capabilities):
        blockers.append({"code": "github.capability.missing", "message": f"explicit {capability} grant required"})
    if contract["risk"] != "read" and not confirmed:
        blockers.append({"code": "github.confirmation.required", "message": "write confirmation required"})
    return {
        "allowed": not blockers,
        "mode": selected_mode,
        "adapter": contract["adapter"],
        "operation": contract["operation"],
        "capability": capability,
        "risk": contract["risk"],
        "blockers": blockers,
    }


def _required(payload: dict, key: str, kind: str) -> object:
    value = payload.get(key)
    if value is None or value == "":
        raise GitHubDeliveryError("github.fact.missing", f"{kind} is missing {key}")
    return value


def _state(value: object) -> str:
    return str(value).strip().casefold().replace("_", "-")


def _external_url(project: str, value: object, suffix: str, origin: str | None = None) -> tuple[str, str]:
    url = str(value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise GitHubDeliveryError("github.fact.url", f"invalid GitHub evidence URL {url!r}")
    if parsed.path.rstrip("/") != f"/{project}/{suffix}":
        raise GitHubDeliveryError("github.fact.project", f"GitHub evidence URL does not belong to {project}")
    current_origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin is not None and current_origin != origin:
        raise GitHubDeliveryError("github.fact.origin", "GitHub evidence URLs must share one origin")
    return url, current_origin


def normalize_delivery(
    *,
    project: str,
    expected_revision: str,
    issue: dict,
    pull_request: dict,
    check_run: dict,
) -> dict:
    """Normalize one coherent GitHub observation and fail closed on stale evidence."""
    revision = expected_revision.casefold()
    if not SHA.fullmatch(revision):
        raise GitHubDeliveryError("github.revision.invalid", "expected revision must be a full commit SHA")
    issue_state = _state(_required(issue, "state", "issue"))
    if issue_state not in {"open", "closed"}:
        raise GitHubDeliveryError("github.issue.state", f"unsupported issue state {issue_state!r}")
    issue_id = str(_required(issue, "number", "issue"))
    pull_request_id = str(_required(pull_request, "number", "pull request"))
    run_id = str(_required(check_run, "databaseId", "check run"))
    issue_url, origin = _external_url(project, _required(issue, "url", "issue"), f"issues/{issue_id}")
    pull_request_url, _ = _external_url(
        project,
        _required(pull_request, "url", "pull request"),
        f"pull/{pull_request_id}",
        origin,
    )
    run_url, _ = _external_url(project, _required(check_run, "url", "check run"), f"actions/runs/{run_id}", origin)
    rollup = pull_request.get("statusCheckRollup")
    if not isinstance(rollup, list):
        raise GitHubDeliveryError("github.pr.checks", "pull request statusCheckRollup must be an array")
    matching = [item for item in rollup if isinstance(item, dict) and item.get("detailsUrl") == run_url]
    blockers: list[dict[str, str]] = []

    def block(code: str, message: str) -> None:
        blockers.append({"code": code, "message": message})

    branch = str(_required(pull_request, "headRefName", "pull request"))
    run_revision = str(_required(check_run, "headSha", "check run")).casefold()
    if run_revision != revision:
        block("github.check.stale", "check run does not target the expected commit")
    if str(_required(check_run, "headBranch", "check run")) != branch:
        block("github.check.branch", "check run branch does not match the pull request")
    if not matching:
        block("github.check.unbound", "check run is not present in the pull request check rollup")
    elif any(_state(item.get("conclusion") or item.get("state")) not in SUCCESS for item in matching):
        block("github.check.unsuccessful", "pull request check rollup is not successful")
    if _state(_required(check_run, "status", "check run")) != "completed":
        block("github.check.pending", "check run is not completed")
    if _state(_required(check_run, "conclusion", "check run")) not in SUCCESS:
        block("github.check.unsuccessful", "check run did not succeed")
    if _state(_required(pull_request, "reviewDecision", "pull request")) != "approved":
        block("github.review.unapproved", "pull request review decision is not approved")
    pull_request_state = _state(_required(pull_request, "state", "pull request"))
    if pull_request_state not in {"open", "merged"}:
        block("github.pr.closed", "pull request is closed without merge")
    if pull_request.get("isDraft") is not False:
        block("github.pr.draft", "pull request must not be a draft")

    snapshot = {
        "schema": "agora-ai-sdlc/github-delivery-fact/v1",
        "provider": "github",
        "project": project,
        "expected_revision": revision,
        "unit_of_work": {
            "external_id": issue_id,
            "state": issue_state,
            "url": issue_url,
        },
        "implementation": {
            "external_id": pull_request_id,
            "state": pull_request_state,
            "branch": branch,
            "base": str(_required(pull_request, "baseRefName", "pull request")),
            "url": pull_request_url,
        },
        "review": {"decision": _state(pull_request["reviewDecision"]), "url": pull_request_url},
        "verification": {
            "external_id": run_id,
            "status": _state(check_run["status"]),
            "conclusion": _state(check_run["conclusion"]),
            "revision": run_revision,
            "url": run_url,
        },
        "evidence_references": [
            issue_url,
            pull_request_url,
            f"{run_url}#commit={run_revision}",
        ],
        "allowed": not blockers,
        "blockers": blockers,
    }
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    snapshot["fingerprint"] = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return snapshot


def ingest_snapshot(existing: Iterable[dict], candidate: dict) -> tuple[tuple[dict, ...], bool]:
    """Append a new immutable observation once; unchanged retries are no-ops."""
    snapshots = tuple(existing)
    if any(item.get("fingerprint") == candidate.get("fingerprint") for item in snapshots):
        return snapshots, False
    return (*snapshots, candidate), True
