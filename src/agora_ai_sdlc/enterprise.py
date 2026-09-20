"""Enterprise policy validation and signed project-registry consumption."""

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml
from agora.model import AddRegistryTrustKeyInput, InstallRegistryInput, UpdateRegistryInput
from agora.registry_distribution import inspect_registry_release
from agora.trust import trust_key_from_pem
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.depth_profiles import asset_root

SCHEMA = "agora-ai-sdlc/enterprise-config/v1"
PROFILE_SCHEMA = "agora-ai-sdlc/adoption-profile/v1"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
NAME = re.compile(r"^[a-z][a-z0-9_.-]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EnterpriseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def load_profile() -> dict:
    path = asset_root("profiles") / "enterprise" / "profile.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA or data.get("id") != "enterprise":
        raise EnterpriseError("enterprise.profile.invalid", "invalid Enterprise profile")
    registry = data.get("registry")
    if not isinstance(registry, dict) or registry.get("scope") != "project":
        raise EnterpriseError("enterprise.profile.registry", "Enterprise registries must use project scope")
    if registry.get("minimum_signature_threshold") != 1 or registry.get("signature") != "ed25519":
        raise EnterpriseError("enterprise.profile.signature", "Enterprise requires signed Ed25519 releases")
    return data


def _slug(value: object, field: str) -> str:
    text = str(value) if value is not None else ""
    if not SLUG.fullmatch(text):
        raise EnterpriseError("enterprise.config.slug", f"invalid {field}")
    return text


def _names(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise EnterpriseError("enterprise.config.list", f"{field} must be a non-empty list")
    result = tuple(str(item) for item in value)
    if len(set(result)) != len(result) or any(NAME.fullmatch(item) is None for item in result):
        raise EnterpriseError("enterprise.config.list", f"{field} contains invalid or duplicate values")
    return result


def _limits(value: object, field: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise EnterpriseError("enterprise.config.budget", f"{field} must define budget dimensions")
    limits: dict[str, int] = {}
    for dimension, amount in value.items():
        if (
            not isinstance(dimension, str)
            or NAME.fullmatch(dimension) is None
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
        ):
            raise EnterpriseError("enterprise.config.budget", f"invalid {field} entry")
        limits[dimension] = amount
    return dict(sorted(limits.items()))


def _source(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnterpriseError("enterprise.config.source", "registry source is required")
    source = value.strip()
    parsed = urlparse(source)
    if parsed.scheme:
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise EnterpriseError("enterprise.config.source", "registry URL must be credential-free HTTPS")
        if parsed.query or parsed.fragment:
            raise EnterpriseError("enterprise.config.source", "registry URL must not contain query or fragment data")
        return source
    return str(Path(source).expanduser().resolve())


def _exceptions(value: object) -> tuple[dict[str, str], ...]:
    fields = tuple(load_profile()["exception_required_fields"])
    required = set(fields)
    if not isinstance(value, list):
        raise EnterpriseError("enterprise.config.exception", "exceptions must be a list")
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != required:
            raise EnterpriseError("enterprise.config.exception", "exception fields are invalid")
        normalized = {key: str(item[key]).strip() for key in fields}
        if any(not text for text in normalized.values()):
            raise EnterpriseError("enterprise.config.exception", "exception fields must not be empty")
        _slug(normalized["id"], "exception id")
        try:
            expiry = datetime.fromisoformat(normalized["expires_at"])
        except ValueError as error:
            raise EnterpriseError("enterprise.config.exception", "exception expiry must be ISO 8601") from error
        if expiry.tzinfo is None:
            raise EnterpriseError("enterprise.config.exception", "exception expiry must include a timezone")
        result.append(normalized)
    ids = [item["id"] for item in result]
    if len(ids) != len(set(ids)):
        raise EnterpriseError("enterprise.config.exception", "exception ids must be unique")
    return tuple(result)


def validate_config(config: dict) -> dict:
    top = {"schema", "profile", "organization_policy", "project_customization"}
    if not isinstance(config, dict) or set(config) != top or config.get("schema") != SCHEMA:
        raise EnterpriseError("enterprise.config.fields", "invalid Enterprise configuration fields")
    if config.get("profile") != "enterprise":
        raise EnterpriseError("enterprise.config.profile", "profile must be 'enterprise'")
    organization = config["organization_policy"]
    project = config["project_customization"]
    org_fields = {"registry", "allowed_providers", "budget_ceilings", "required_metrics"}
    project_fields = {"project_id", "providers", "budgets", "exported_metrics", "exceptions"}
    if not isinstance(organization, dict) or set(organization) != org_fields:
        raise EnterpriseError("enterprise.config.organization", "organization policy fields are invalid")
    if not isinstance(project, dict) or set(project) != project_fields:
        raise EnterpriseError("enterprise.config.project", "project customization fields are invalid")

    registry = organization["registry"]
    registry_fields = {"id", "source", "version", "signature_threshold", "trust_keys"}
    if not isinstance(registry, dict) or set(registry) != registry_fields:
        raise EnterpriseError("enterprise.config.registry", "registry policy fields are invalid")
    threshold = registry["signature_threshold"]
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 1:
        raise EnterpriseError("enterprise.config.signature", "signature threshold must be a positive integer")
    keys = registry["trust_keys"]
    if not isinstance(keys, list) or len(keys) < threshold:
        raise EnterpriseError("enterprise.config.signature", "not enough trust keys for signature threshold")
    normalized_keys = []
    for key in keys:
        if not isinstance(key, dict) or set(key) != {"id", "public_key"}:
            raise EnterpriseError("enterprise.config.signature", "trust key fields are invalid")
        normalized_keys.append(
            {"id": _slug(key["id"], "trust key id"), "public_key": str(Path(key["public_key"]).resolve())}
        )
    if len({key["id"] for key in normalized_keys}) != len(normalized_keys):
        raise EnterpriseError("enterprise.config.signature", "trust key ids must be unique")

    allowed = _names(organization["allowed_providers"], "allowed providers")
    providers = _names(project["providers"], "project providers")
    if not set(providers) <= set(allowed):
        raise EnterpriseError("enterprise.config.provider", "project provider is not allowed by organization policy")
    ceilings = _limits(organization["budget_ceilings"], "organization budget ceilings")
    budgets = _limits(project["budgets"], "project budgets")
    if set(budgets) != set(ceilings) or any(budgets[key] > ceilings[key] for key in ceilings):
        raise EnterpriseError("enterprise.config.budget", "project budgets must cover and stay within every ceiling")
    required_metrics = _names(organization["required_metrics"], "required metrics")
    exported_metrics = _names(project["exported_metrics"], "exported metrics")
    if not set(required_metrics) <= set(exported_metrics):
        raise EnterpriseError("enterprise.config.metric", "project does not export every required metric")

    return {
        "schema": SCHEMA,
        "profile": "enterprise",
        "organization_policy": {
            "registry": {
                "id": _slug(registry["id"], "registry id"),
                "source": _source(registry["source"]),
                "version": str(registry["version"]),
                "signature_threshold": threshold,
                "trust_keys": tuple(normalized_keys),
            },
            "allowed_providers": allowed,
            "budget_ceilings": ceilings,
            "required_metrics": required_metrics,
        },
        "project_customization": {
            "project_id": _slug(project["project_id"], "project id"),
            "providers": providers,
            "budgets": budgets,
            "exported_metrics": exported_metrics,
            "exceptions": _exceptions(project["exceptions"]),
        },
    }


def _candidate_keys(policy: dict) -> list:
    registry = policy["registry"]
    return [
        trust_key_from_pem(
            id_=key["id"],
            registry=registry["id"],
            public_key_path=Path(key["public_key"]),
            scope="project",
            path=Path("preview") / f"{key['id']}.md",
            created_at="preview",
        )
        for key in registry["trust_keys"]
    ]


def _effective_keys(workspace: AgoraWorkspace, candidates: list) -> list:
    try:
        installed = workspace.list_registry_trust_keys()
    except FileNotFoundError:
        installed = []
    configured_ids = {candidate.id for candidate in candidates}
    registry_id = candidates[0].registry
    unmanaged = sorted(key.id for key in installed if key.registry == registry_id and key.id not in configured_ids)
    if unmanaged:
        raise EnterpriseError(
            "enterprise.trust.unmanaged",
            f"installed registry trust keys are absent from organization policy: {', '.join(unmanaged)}",
        )
    effective = []
    for candidate in candidates:
        matches = [key for key in installed if key.id == candidate.id]
        if matches:
            if any(
                current.registry != candidate.registry or current.fingerprint != candidate.fingerprint
                for current in matches
            ):
                raise EnterpriseError("enterprise.trust.conflict", f"trust key {candidate.id!r} conflicts with policy")
            effective.append(next((current for current in matches if current.status == "revoked"), matches[0]))
        else:
            effective.append(candidate)
    return effective


def preview_install(config: dict, target: Path) -> dict:
    normalized = validate_config(config)
    policy = normalized["organization_policy"]
    registry = policy["registry"]
    workspace = AgoraWorkspace(cwd=target)
    candidates = _candidate_keys(policy)
    effective = _effective_keys(workspace, candidates)
    index, release, verified = inspect_registry_release(
        registry["source"],
        version=registry["version"],
        public_key=None,
        require_signature=True,
        signature_threshold=registry["signature_threshold"],
        allow_insecure_http=False,
        trusted_keys=effective,
    )
    if index.id != registry["id"]:
        raise EnterpriseError("enterprise.registry.id", "registry index does not match organization policy")
    return {
        "schema": "agora-ai-sdlc/enterprise-registry-preview/v1",
        "operation": "install",
        "project": normalized["project_customization"]["project_id"],
        "registry": registry["id"],
        "version": release.version,
        "checksum": release.sha256,
        "signature_threshold": registry["signature_threshold"],
        "verified_key_ids": tuple(verified),
        "writes": ("project trust keys", f".agora/registries/{registry['id']}"),
    }


def install(config: dict, target: Path) -> dict:
    normalized = validate_config(config)
    plan = preview_install(config, target)
    workspace = AgoraWorkspace(cwd=target)
    policy = normalized["organization_policy"]
    candidates = _candidate_keys(policy)
    installed = {key.id: key for key in workspace.list_registry_trust_keys() if key.scope == "project"}
    for candidate, configured in zip(candidates, policy["registry"]["trust_keys"], strict=True):
        if candidate.id not in installed:
            workspace.add_registry_trust_key(
                AddRegistryTrustKeyInput(
                    id=candidate.id,
                    registry_id=candidate.registry,
                    public_key=configured["public_key"],
                    scope="project",
                )
            )
    registry = policy["registry"]
    snapshot = workspace.install_registry(
        InstallRegistryInput(
            source=registry["source"],
            scope="project",
            version=registry["version"],
            require_signature=True,
            signature_threshold=registry["signature_threshold"],
        )
    )
    if (
        snapshot.id != plan["registry"]
        or snapshot.version != plan["version"]
        or snapshot.checksum != plan["checksum"]
        or not snapshot.signature_verified
        or snapshot.scope != "project"
        or snapshot.signature_threshold != plan["signature_threshold"]
        or set(snapshot.verified_key_ids) != set(plan["verified_key_ids"])
    ):
        raise RuntimeError("Installed registry snapshot differs from reviewed preview")
    return {**plan, "operation": "installed", "provenance": str(Path(snapshot.path) / "SOURCE.md")}


def _installed(workspace: AgoraWorkspace, registry_id: str):
    matches = [item for item in workspace.list_registries() if item.id == registry_id and item.scope == "project"]
    if len(matches) != 1:
        raise EnterpriseError(
            "enterprise.registry.installed", "project registry snapshot is not installed exactly once"
        )
    return matches[0]


def preview_upgrade(config: dict, target: Path) -> dict:
    normalized = validate_config(config)
    policy = normalized["organization_policy"]
    registry = policy["registry"]
    workspace = AgoraWorkspace(cwd=target)
    current = _installed(workspace, registry["id"])
    _effective_keys(workspace, _candidate_keys(policy))
    result = workspace.update_registry(
        UpdateRegistryInput(
            id=registry["id"],
            scope="project",
            version=registry["version"],
            apply=False,
            require_signature=True,
            signature_threshold=registry["signature_threshold"],
        )
    )
    return {
        "schema": "agora-ai-sdlc/enterprise-registry-upgrade/v1",
        "operation": "upgrade",
        "registry": result.registry,
        "from_version": result.from_version,
        "to_version": result.to_version,
        "checksum": result.checksum,
        "signature_verified": result.signature_verified,
        "update_available": result.update_available,
        "applied": False,
        "rollback": {
            "strategy": "signed-forward-release",
            "content_version": current.version,
            "content_checksum": current.checksum,
        },
    }


def apply_upgrade(config: dict, target: Path, *, reviewed_checksum: str) -> dict:
    if SHA256.fullmatch(reviewed_checksum) is None:
        raise EnterpriseError("enterprise.upgrade.checksum", "reviewed checksum must be lowercase SHA-256")
    plan = preview_upgrade(config, target)
    if not plan["update_available"]:
        return plan
    if plan["checksum"] != reviewed_checksum:
        raise EnterpriseError("enterprise.upgrade.review", "upgrade checksum differs from reviewed preview")
    normalized = validate_config(config)
    registry = normalized["organization_policy"]["registry"]
    workspace = AgoraWorkspace(cwd=target)
    result = workspace.update_registry(
        UpdateRegistryInput(
            id=registry["id"],
            scope="project",
            version=registry["version"],
            apply=True,
            require_signature=True,
            signature_threshold=registry["signature_threshold"],
        )
    )
    if result.checksum != reviewed_checksum or not result.signature_verified or not result.applied:
        raise RuntimeError("Applied registry upgrade differs from reviewed preview")
    snapshot = _installed(workspace, registry["id"])
    configured_ids = {key["id"] for key in registry["trust_keys"]}
    if (
        snapshot.signature_threshold != registry["signature_threshold"]
        or len(snapshot.verified_key_ids) < registry["signature_threshold"]
        or not set(snapshot.verified_key_ids) <= configured_ids
    ):
        raise RuntimeError("Applied registry upgrade has unexpected signature provenance")
    return {**plan, "applied": True, "record_path": result.record_path}
