"""GitLab and Jira mappings over provider-neutral Agora Core capabilities."""

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
JIRA_KEY = re.compile(r"^[A-Z][A-Z0-9_]*-[1-9][0-9]*$")
POSITIVE_ID = re.compile(r"^[1-9][0-9]*$")
GITLAB_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PROVIDERS = {"gitlab", "jira"}
SUCCESS = {"success", "successful", "passed"}


class FollowOnDeliveryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def load_profile(provider: str) -> dict:
    if provider not in PROVIDERS:
        raise FollowOnDeliveryError("integration.provider.unknown", f"unknown provider {provider!r}")
    path = asset_root("profiles") / "integrations" / provider / "profile.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected_id = "gitlab-delivery" if provider == "gitlab" else "jira-work-management"
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("id") != expected_id:
        raise FollowOnDeliveryError(f"{provider}.profile.invalid", f"invalid {provider} integration profile")
    if data.get("provider") != provider or data.get("default_mode") != "read-only":
        raise FollowOnDeliveryError(
            f"{provider}.profile.default", "profile must identify its provider and default read-only"
        )
    return data


def install_read_only(provider: str, workspace, project_root: Path) -> tuple[str, ...]:
    """Install reviewed Core adapters and add only declared read capabilities."""
    profile = load_profile(provider)
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
    provider: str,
    operation: str,
    *,
    mode: str | None = None,
    granted_capabilities: Iterable[str] = (),
    confirmed: bool = False,
) -> dict:
    """Evaluate opt-in permission policy without invoking a provider."""
    profile = load_profile(provider)
    selected_mode = mode or profile["default_mode"]
    if selected_mode not in profile["modes"]:
        raise FollowOnDeliveryError(f"{provider}.mode.unknown", f"unknown permission mode {selected_mode!r}")
    if operation not in profile["operations"]:
        qualifier = "unsupported" if operation in profile.get("unsupported", ()) else "unknown"
        raise FollowOnDeliveryError(
            f"{provider}.operation.{qualifier}",
            f"{operation!r} is {qualifier} by the {provider} profile",
        )
    contract = profile["operations"][operation]
    capability = contract["capability"]
    policy_capabilities = set(profile["modes"][selected_mode]["capabilities"])
    blockers = []
    if capability not in policy_capabilities:
        blockers.append({"code": f"{provider}.mode.denied", "message": f"{selected_mode} does not permit {capability}"})
    if contract["risk"] != "read" and capability not in set(granted_capabilities):
        blockers.append({"code": f"{provider}.capability.missing", "message": f"explicit {capability} grant required"})
    if contract["risk"] != "read" and not confirmed:
        blockers.append({"code": f"{provider}.confirmation.required", "message": "write confirmation required"})
    return {
        "allowed": not blockers,
        "provider": provider,
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
        raise FollowOnDeliveryError("integration.fact.missing", f"{kind} is missing {key}")
    return value


def _state(value: object) -> str:
    return str(value).strip().casefold().replace("_", "-").replace(" ", "-")


def _url(value: object, *, origin: str | None = None, exact_path: str | None = None) -> tuple[str, str]:
    url = str(value)
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise FollowOnDeliveryError("integration.fact.url", f"unsafe external evidence URL {url!r}")
    current_origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin is not None and current_origin != origin.rstrip("/"):
        raise FollowOnDeliveryError("integration.fact.origin", "external evidence URL has an unexpected origin")
    if exact_path is not None and parsed.path.rstrip("/") != exact_path.rstrip("/"):
        raise FollowOnDeliveryError("integration.fact.path", "external evidence URL does not match its external id")
    return url, current_origin


def _fingerprint(snapshot: dict) -> dict:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    snapshot["fingerprint"] = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return snapshot


def _positive_id(value: object, kind: str) -> str:
    external_id = str(value)
    if not POSITIVE_ID.fullmatch(external_id):
        raise FollowOnDeliveryError("gitlab.id.invalid", f"invalid {kind} id {external_id!r}")
    return external_id


def _gitlab_project(value: str) -> str:
    if not value or value.startswith("//") or value.endswith("/") or "//" in value:
        raise FollowOnDeliveryError("gitlab.project.invalid", f"invalid GitLab project path {value!r}")
    project = value.removeprefix("/")
    segments = project.split("/")
    if len(segments) < 2 or any(
        segment in {"", ".", ".."} or not GITLAB_PATH_SEGMENT.fullmatch(segment) for segment in segments
    ):
        raise FollowOnDeliveryError("gitlab.project.invalid", f"invalid GitLab project path {value!r}")
    return project


def normalize_work_item(provider: str, *, scope: str, observed_at: str, item: dict) -> dict:
    """Translate a provider work item into stable neutral state semantics."""
    profile = load_profile(provider)
    observation = str(observed_at).strip()
    if not observation:
        raise FollowOnDeliveryError("integration.observation.missing", "observation time is required")
    if provider == "gitlab":
        external_id = _positive_id(_required(item, "iid", "GitLab issue"), "GitLab issue")
        raw_state = _state(_required(item, "state", "GitLab issue"))
        scope_url, scope_origin = _url(scope)
        scope_path = urlparse(scope_url).path.rstrip("/")
        _gitlab_project(scope_path)
        url, _ = _url(
            _required(item, "web_url", "GitLab issue"),
            origin=scope_origin,
            exact_path=f"{scope_path}/-/issues/{external_id}",
        )
    else:
        external_id = str(_required(item, "key", "Jira work item"))
        if not JIRA_KEY.fullmatch(external_id):
            raise FollowOnDeliveryError("jira.key.invalid", f"invalid Jira work-item key {external_id!r}")
        fields = _required(item, "fields", "Jira work item")
        if not isinstance(fields, dict) or not isinstance(fields.get("status"), dict):
            raise FollowOnDeliveryError("integration.fact.missing", "Jira work item is missing fields.status")
        raw_state = _state(_required(fields["status"], "name", "Jira status"))
        scope_url, scope_origin = _url(scope, exact_path="/")
        url, _ = _url(
            f"{scope_url.rstrip('/')}/browse/{external_id}",
            origin=scope_origin,
            exact_path=f"/browse/{external_id}",
        )
    state = profile["state_mapping"].get(raw_state)
    if state is None:
        raise FollowOnDeliveryError(f"{provider}.state.unsupported", f"unsupported external state {raw_state!r}")
    return _fingerprint(
        {
            "schema": "agora-ai-sdlc/work-item-fact/v1",
            "source": {
                "provider": provider,
                "scope": scope,
                "external_id": external_id,
                "external_state": raw_state,
                "observed_at": observation,
                "url": url,
            },
            "outcome": {"state": state, "terminal": state == "closed"},
        }
    )


def normalize_gitlab_delivery(
    *,
    project: str,
    origin: str,
    expected_revision: str,
    observed_at: str,
    issue: dict,
    merge_request: dict,
    pipeline: dict,
) -> dict:
    """Normalize one coherent GitLab delivery observation at an exact commit."""
    revision = expected_revision.casefold()
    if not SHA.fullmatch(revision):
        raise FollowOnDeliveryError("gitlab.revision.invalid", "expected revision must be a full commit SHA")
    project = _gitlab_project(project)
    origin, _ = _url(origin, exact_path="/")
    scope = f"{origin.rstrip('/')}/{project}"
    work_item = normalize_work_item("gitlab", scope=scope, observed_at=observed_at, item=issue)
    merge_id = _positive_id(_required(merge_request, "iid", "GitLab merge request"), "GitLab merge request")
    merge_url, _ = _url(
        _required(merge_request, "web_url", "GitLab merge request"),
        origin=origin,
        exact_path=f"/{project}/-/merge_requests/{merge_id}",
    )
    pipeline_id = _positive_id(_required(pipeline, "id", "GitLab pipeline"), "GitLab pipeline")
    pipeline_url, _ = _url(
        _required(pipeline, "web_url", "GitLab pipeline"),
        origin=origin,
        exact_path=f"/{project}/-/pipelines/{pipeline_id}",
    )
    blockers: list[dict[str, str]] = []

    def block(code: str, message: str) -> None:
        blockers.append({"code": code, "message": message})

    pipeline_revision = str(_required(pipeline, "sha", "GitLab pipeline")).casefold()
    if pipeline_revision != revision:
        block("gitlab.pipeline.stale", "pipeline does not target the expected commit")
    if _state(_required(pipeline, "status", "GitLab pipeline")) not in SUCCESS:
        block("gitlab.pipeline.unsuccessful", "pipeline did not succeed")
    branch = str(_required(merge_request, "source_branch", "GitLab merge request"))
    if str(_required(pipeline, "ref", "GitLab pipeline")) != branch:
        block("gitlab.pipeline.branch", "pipeline ref does not match the merge request")
    head_pipeline = _required(merge_request, "head_pipeline", "GitLab merge request")
    if not isinstance(head_pipeline, dict) or str(head_pipeline.get("id")) != pipeline_id:
        block("gitlab.pipeline.unbound", "pipeline is not the merge request head pipeline")
    if merge_request.get("approved") is not True:
        block("gitlab.review.unapproved", "merge request is not approved")
    if merge_request.get("draft") is not False:
        block("gitlab.review.draft", "merge request must not be a draft")
    merge_state = _state(_required(merge_request, "state", "GitLab merge request"))
    if merge_state not in {"opened", "merged"}:
        block("gitlab.review.closed", "merge request is closed without merge")

    return _fingerprint(
        {
            "schema": "agora-ai-sdlc/delivery-fact/v1",
            "provider": "gitlab",
            "project": project,
            "expected_revision": revision,
            "source": {
                "provider": "gitlab",
                "scope": scope,
                "external_id": pipeline_id,
                "observed_at": work_item["source"]["observed_at"],
            },
            "unit_of_work": work_item,
            "implementation": {
                "external_id": merge_id,
                "state": "open" if merge_state == "opened" else "merged",
                "branch": branch,
                "base": str(_required(merge_request, "target_branch", "GitLab merge request")),
                "url": merge_url,
            },
            "review": {
                "decision": "approved" if merge_request.get("approved") is True else "unapproved",
                "url": merge_url,
            },
            "verification": {
                "external_id": pipeline_id,
                "status": _state(pipeline["status"]),
                "revision": pipeline_revision,
                "url": pipeline_url,
            },
            "evidence_references": [
                work_item["source"]["url"],
                merge_url,
                f"{pipeline_url}#commit={pipeline_revision}",
            ],
            "allowed": not blockers,
            "blockers": blockers,
        }
    )


def reconcile_observation(existing: Iterable[dict], candidate: dict) -> tuple[tuple[dict, ...], bool]:
    """Append changed source facts, reject mutation at one source revision, and deduplicate retries."""
    observations = tuple(existing)
    if any(item.get("fingerprint") == candidate.get("fingerprint") for item in observations):
        return observations, False
    source = candidate.get("source")
    if isinstance(source, dict):
        identity = (source.get("provider"), source.get("scope"), source.get("external_id"), source.get("observed_at"))
        for item in observations:
            previous = item.get("source")
            if isinstance(previous, dict):
                previous_identity = (
                    previous.get("provider"),
                    previous.get("scope"),
                    previous.get("external_id"),
                    previous.get("observed_at"),
                )
                if previous_identity == identity:
                    raise FollowOnDeliveryError(
                        "integration.reconciliation.conflict", "source revision changed in place"
                    )
    return (*observations, candidate), True
