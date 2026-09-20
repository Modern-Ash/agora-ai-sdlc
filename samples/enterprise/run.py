"""Credential-free signed-registry Enterprise profile sample."""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from agora.markdown import MarkdownDocument, render_markdown
from agora.model import InitInput, RegistryReleaseRecord
from agora.registry_distribution import release_signature_payload
from agora.workspace import AgoraWorkspace
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.enterprise import apply_upgrade, install, preview_install, preview_upgrade


def _archive(root: Path, version: str) -> tuple[str, str]:
    name = f"organization-registry-{version}.zip"
    path = root / name
    metadata = (
        "---\n"
        "schema: agora/registry/v1\n"
        "id: organization-registry\n"
        "name: Example organization registry\n"
        f"version: {version}\n"
        "---\n# Example organization registry\n"
    )
    info = zipfile.ZipInfo("organization-registry/REGISTRY.md", date_time=(2020, 1, 1, 0, 0, 0))
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr(info, metadata)
        method = asset_root("registry") / "methods" / "ai-sdlc"
        for source in sorted(item for item in method.rglob("*") if item.is_file()):
            relative = source.relative_to(method)
            pack_info = zipfile.ZipInfo(
                f"organization-registry/methods/ai-sdlc/{relative.as_posix()}",
                date_time=(2020, 1, 1, 0, 0, 0),
            )
            bundle.writestr(pack_info, source.read_bytes())
    return name, hashlib.sha256(path.read_bytes()).hexdigest()


def _write_index(root: Path, private_key: Ed25519PrivateKey, versions: list[str]) -> Path:
    releases = []
    for version in versions:
        archive, checksum = _archive(root, version)
        release = RegistryReleaseRecord("organization-registry", version, archive, checksum)
        signature = base64.b64encode(private_key.sign(release_signature_payload(release))).decode()
        releases.append(
            {
                "version": version,
                "archive": archive,
                "sha256": checksum,
                "signatures": [{"key-id": "organization-release", "signature": signature}],
            }
        )
    index = root / "INDEX.md"
    attributes = {
        "schema": "agora/registry-index/v1",
        "id": "organization-registry",
        "name": "Example organization registry",
        "releases": releases,
    }
    index.write_text(render_markdown(MarkdownDocument(attributes, "# Releases")), encoding="utf-8")
    return index


def _config(index: Path, public_key: Path, version: str) -> dict:
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
            "budget_ceilings": {"requests": 1000, "tokens": 100000},
            "required_metrics": ["change_failure_rate", "deployment_frequency"],
        },
        "project_customization": {
            "project_id": "payments-api",
            "providers": ["local"],
            "budgets": {"requests": 500, "tokens": 50000},
            "exported_metrics": ["change_failure_rate", "deployment_frequency", "lead_time"],
            "exceptions": [],
        },
    }


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-enterprise-"))
    project, home, registry_root = runtime / "project", runtime / "home", runtime / "distribution"
    project.mkdir()
    registry_root.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    os.environ["AGORA_HOME"] = str(home)
    AgoraWorkspace(cwd=project).initialize(
        InitInput(integration="generic", provider="local", model="human", default_method="scrum")
    )

    private_key = Ed25519PrivateKey.generate()
    public_key = registry_root / "organization-release.pem"
    public_key.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    index = _write_index(registry_root, private_key, ["1.0.0"])
    initial = _config(index, public_key, "1.0.0")
    install_plan = preview_install(initial, project)
    installed = install(initial, project)

    _write_index(registry_root, private_key, ["2.0.0", "1.0.0"])
    upgrade_config = _config(index, public_key, "2.0.0")
    upgrade_plan = preview_upgrade(upgrade_config, project)
    upgraded = apply_upgrade(upgrade_config, project, reviewed_checksum=upgrade_plan["checksum"])
    snapshot = next(
        item
        for item in AgoraWorkspace(cwd=project).list_registries()
        if item.id == "organization-registry" and item.scope == "project"
    )
    summary = {
        "final_state": "completed" if snapshot.version == "2.0.0" else "failed",
        "validate": "ok" if snapshot.signature_verified else "failed",
        "profile": "enterprise",
        "install_preview_matches": install_plan["checksum"] == installed["checksum"],
        "upgrade_previewed": upgrade_plan["update_available"],
        "upgrade_applied": upgraded["applied"],
        "signature_verified": snapshot.signature_verified,
        "provenance_recorded": (Path(snapshot.path) / "SOURCE.md").is_file(),
        "rollback_strategy": upgraded["rollback"]["strategy"],
    }
    print(json.dumps(summary, sort_keys=True))
    if summary["final_state"] == "completed" and summary["validate"] == "ok":
        shutil.rmtree(runtime)
    else:
        summary["workspace"] = str(project)
    return summary


if __name__ == "__main__":
    main()
