import base64
import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest
from agora.markdown import MarkdownDocument, parse_markdown, render_markdown
from agora.model import (
    AddRegistryTrustKeyInput,
    InitInput,
    RegistryReleaseRecord,
    RevokeRegistryTrustKeyInput,
)
from agora.registries import read_registry_source, read_registry_update
from agora.registry_distribution import release_signature_payload
from agora.workspace import AgoraWorkspace
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.enterprise import (
    EnterpriseError,
    apply_upgrade,
    install,
    load_profile,
    preview_install,
    preview_upgrade,
    validate_config,
)


def _project(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    AgoraWorkspace(cwd=project).initialize(
        InitInput(integration="generic", provider="local", model="human", default_method="scrum")
    )
    return project


def _public_key(root: Path, private_key: Ed25519PrivateKey, name: str = "release") -> Path:
    path = root / f"{name}.pem"
    path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return path


def _release(root: Path, private_key: Ed25519PrivateKey, version: str, *, advertised: str | None = None) -> dict:
    archive = root / f"organization-registry-{version}.zip"
    info = zipfile.ZipInfo("organization-registry/REGISTRY.md", date_time=(2020, 1, 1, 0, 0, 0))
    metadata = (
        "---\n"
        "schema: agora/registry/v1\n"
        "id: organization-registry\n"
        "name: Organization registry\n"
        f"version: {version}\n"
        "---\n# Organization registry\n"
    )
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(info, metadata)
        method = asset_root("registry") / "methods" / "ai-sdlc"
        for source in sorted(item for item in method.rglob("*") if item.is_file()):
            relative = source.relative_to(method)
            pack_info = zipfile.ZipInfo(
                f"organization-registry/methods/ai-sdlc/{relative.as_posix()}",
                date_time=(2020, 1, 1, 0, 0, 0),
            )
            bundle.writestr(pack_info, source.read_bytes())
    checksum = advertised or hashlib.sha256(archive.read_bytes()).hexdigest()
    record = RegistryReleaseRecord("organization-registry", version, archive.name, checksum)
    signature = base64.b64encode(private_key.sign(release_signature_payload(record))).decode()
    return {
        "version": version,
        "archive": archive.name,
        "sha256": checksum,
        "signatures": [{"key-id": "organization-release", "signature": signature}],
    }


def _index(root: Path, releases: list[dict]) -> Path:
    attributes = {
        "schema": "agora/registry-index/v1",
        "id": "organization-registry",
        "name": "Organization registry",
        "releases": releases,
    }
    path = root / "INDEX.md"
    path.write_text(render_markdown(MarkdownDocument(attributes, "# Releases")), encoding="utf-8")
    return path


def _config(index: Path, public_key: Path, version: str = "1.0.0") -> dict:
    return {
        "schema": "agora-ai-sdlc/enterprise-config/v1",
        "profile": "enterprise",
        "organization_policy": {
            "registry": {
                "id": "organization-registry",
                "source": str(index),
                "version": version,
                "signature_threshold": 1,
                "trust_keys": [{"id": "organization-release", "public_key": str(public_key)}],
            },
            "allowed_providers": ["local", "reviewed-cloud"],
            "budget_ceilings": {"requests": 100, "tokens": 1000},
            "required_metrics": ["change_failure_rate", "deployment_frequency"],
        },
        "project_customization": {
            "project_id": "payments-api",
            "providers": ["local"],
            "budgets": {"requests": 50, "tokens": 800},
            "exported_metrics": ["change_failure_rate", "deployment_frequency", "lead_time"],
            "exceptions": [],
        },
    }


def _distribution(tmp_path, versions=("1.0.0",)):
    root = tmp_path / "distribution"
    root.mkdir()
    private_key = Ed25519PrivateKey.generate()
    public_key = _public_key(root, private_key)
    releases = [_release(root, private_key, version) for version in versions]
    return root, private_key, public_key, _index(root, releases)


def _files(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_profile_declares_project_scoped_signed_snapshots_and_separate_fields():
    profile = load_profile()
    assert profile["extends"] == "starter" and profile["depth"] == "comprehensive"
    assert profile["registry"] == {
        "scope": "project",
        "checksum": "sha256",
        "signature": "ed25519",
        "minimum_signature_threshold": 1,
        "immutable_snapshot": True,
        "provenance_record": "SOURCE.md",
    }
    assert set(profile["organization_policy_fields"]).isdisjoint(profile["project_customization_fields"])


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda c: c["project_customization"].update(providers=["unapproved"]), "enterprise.config.provider"),
        (lambda c: c["project_customization"]["budgets"].update(tokens=1001), "enterprise.config.budget"),
        (
            lambda c: c["project_customization"].update(exported_metrics=["deployment_frequency"]),
            "enterprise.config.metric",
        ),
        (lambda c: c["organization_policy"]["registry"].update(signature_threshold=0), "enterprise.config.signature"),
    ],
)
def test_policy_violations_fail_before_project_writes(tmp_path, mutate, code):
    _, _, public_key, index = _distribution(tmp_path)
    config = _config(index, public_key)
    mutate(config)
    target = tmp_path / "absent-project"
    with pytest.raises(EnterpriseError) as error:
        install(config, target)
    assert error.value.code == code and not target.exists()


def test_valid_signature_preview_is_pure_and_install_records_provenance(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    _, _, public_key, index = _distribution(tmp_path)
    config = _config(index, public_key)
    before = _files(project)
    plan = preview_install(config, project)
    assert _files(project) == before
    result = install(config, project)
    snapshot = next(
        item for item in AgoraWorkspace(cwd=project).list_registries() if item.id == "organization-registry"
    )
    source = read_registry_source(Path(snapshot.path) / "SOURCE.md")
    assert result["checksum"] == plan["checksum"] == source.sha256 == snapshot.checksum
    assert source.signature_verified and source.verified_key_ids == ["organization-release"]
    assert source.signature_threshold == 1 and snapshot.scope == "project"


@pytest.mark.parametrize("failure", ["untrusted", "invalid-signature"])
def test_untrusted_and_invalid_signature_fail_closed(tmp_path, monkeypatch, failure):
    project = _project(tmp_path, monkeypatch)
    root, _, public_key, index = _distribution(tmp_path)
    config = _config(index, public_key)
    if failure == "untrusted":
        public_key = _public_key(root, Ed25519PrivateKey.generate(), "rogue")
        config["organization_policy"]["registry"]["trust_keys"][0]["public_key"] = str(public_key)
    else:
        text = index.read_text(encoding="utf-8")
        signature = parse_markdown(text).attributes["releases"][0]["signatures"][0]["signature"]
        index.write_text(text.replace(signature, base64.b64encode(b"invalid").decode()), encoding="utf-8")
    before = _files(project)
    with pytest.raises(ValueError):
        install(config, project)
    assert _files(project) == before
    assert not (project / ".agora" / "registries" / "organization-registry").exists()


def test_revoked_key_fails_closed_even_when_config_still_declares_it(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    _, _, public_key, index = _distribution(tmp_path)
    workspace = AgoraWorkspace(cwd=project)
    workspace.add_registry_trust_key(
        AddRegistryTrustKeyInput("organization-release", "organization-registry", str(public_key), "project")
    )
    workspace.revoke_registry_trust_key(
        RevokeRegistryTrustKeyInput("organization-release", "project", "organization revocation")
    )
    before = _files(project)
    with pytest.raises(PermissionError, match="revoked"):
        install(_config(index, public_key), project)
    assert _files(project) == before


def test_unmanaged_installed_key_for_registry_blocks_preview(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    root, _, public_key, index = _distribution(tmp_path)
    unmanaged = _public_key(root, Ed25519PrivateKey.generate(), "unmanaged")
    AgoraWorkspace(cwd=project).add_registry_trust_key(
        AddRegistryTrustKeyInput("unmanaged", "organization-registry", str(unmanaged), "project")
    )
    with pytest.raises(EnterpriseError) as error:
        preview_install(_config(index, public_key), project)
    assert error.value.code == "enterprise.trust.unmanaged"


def test_upgrade_preview_apply_history_and_rollback_point(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    root, private_key, public_key, index = _distribution(tmp_path)
    initial = _config(index, public_key)
    installed = install(initial, project)
    _index(root, [_release(root, private_key, "2.0.0"), _release(root, private_key, "1.0.0")])
    upgrade = _config(index, public_key, "2.0.0")
    before = _files(project)
    plan = preview_upgrade(upgrade, project)
    assert _files(project) == before and plan["update_available"] and not plan["applied"]
    assert plan["rollback"]["content_checksum"] == installed["checksum"]
    result = apply_upgrade(upgrade, project, reviewed_checksum=plan["checksum"])
    assert result["applied"] and result["rollback"]["strategy"] == "signed-forward-release"
    update = read_registry_update(Path(result["record_path"]))
    assert update.from_sha256 == installed["checksum"] and update.to_sha256 == plan["checksum"]


def test_upgrade_conflicting_reviewed_checksum_fails_without_mutation(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    root, private_key, public_key, index = _distribution(tmp_path)
    install(_config(index, public_key), project)
    _index(root, [_release(root, private_key, "2.0.0"), _release(root, private_key, "1.0.0")])
    upgrade = _config(index, public_key, "2.0.0")
    before = _files(project)
    with pytest.raises(EnterpriseError) as error:
        apply_upgrade(upgrade, project, reviewed_checksum="0" * 64)
    assert error.value.code == "enterprise.upgrade.review" and _files(project) == before


def test_changed_installed_version_checksum_is_rejected_as_conflict(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    root, private_key, public_key, index = _distribution(tmp_path)
    install(_config(index, public_key), project)
    archive = root / "organization-registry-1.0.0.zip"
    archive.write_bytes(archive.read_bytes() + b"changed")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    record = RegistryReleaseRecord("organization-registry", "1.0.0", archive.name, checksum)
    signature = base64.b64encode(private_key.sign(release_signature_payload(record))).decode()
    _index(
        root,
        [{"version": "1.0.0", "archive": archive.name, "sha256": checksum,
          "signatures": [{"key-id": "organization-release", "signature": signature}]}],
    )  # fmt: skip
    before = _files(project)
    with pytest.raises(ValueError, match="changed checksum"):
        preview_upgrade(_config(index, public_key), project)
    assert _files(project) == before


def test_bad_upgrade_archive_keeps_previous_snapshot(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    root, private_key, public_key, index = _distribution(tmp_path)
    installed = install(_config(index, public_key), project)
    invalid = _release(root, private_key, "2.0.0", advertised="f" * 64)
    _index(root, [invalid, _release(root, private_key, "1.0.0")])
    upgrade = _config(index, public_key, "2.0.0")
    plan = preview_upgrade(upgrade, project)
    with pytest.raises(ValueError, match="checksum mismatch"):
        apply_upgrade(upgrade, project, reviewed_checksum=plan["checksum"])
    snapshot = next(
        item for item in AgoraWorkspace(cwd=project).list_registries() if item.id == "organization-registry"
    )
    assert snapshot.version == "1.0.0" and snapshot.checksum == installed["checksum"]
    assert not (Path(snapshot.path) / "updates").exists()


def test_exception_record_is_auditable_but_does_not_weaken_policy(tmp_path):
    _, _, public_key, index = _distribution(tmp_path)
    config = _config(index, public_key)
    config["project_customization"]["exceptions"] = [
        {
            "id": "temporary-provider-review",
            "policy": "allowed-providers",
            "reason": "migration window",
            "approved_by": "governance-owner",
            "expires_at": "2026-12-01T00:00:00Z",
            "evidence": "decision-42",
        }
    ]
    normalized = validate_config(config)
    assert normalized["project_customization"]["exceptions"][0]["approved_by"] == "governance-owner"
    config["project_customization"]["providers"] = ["unapproved"]
    with pytest.raises(EnterpriseError) as error:
        validate_config(config)
    assert error.value.code == "enterprise.config.provider"
