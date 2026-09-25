"""Git-less local artifact delivery for Agora Flow demos and filesystem workflows."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml
from agora.model import AddEvidenceInput, WorkActorInput
from agora.workspace import AgoraWorkspace

_SKIP_DIRS = {".agora", ".git", ".venv", "node_modules", "dist", "build", "target", "output", "__pycache__"}
_BASELINE_SCHEMA = "agora-ai-sdlc/local-baseline/v1"


@dataclass(frozen=True)
class LocalArtifactDelivery:
    manifest_path: str
    output_path: str
    product_files: tuple[str, ...]
    governance_files: tuple[str, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _project_files(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in _SKIP_DIRS for part in relative.parts):
            continue
        try:
            values[relative.as_posix()] = _sha256(path)
        except OSError:
            continue
    return values


def _baseline_path(root: Path, work: str) -> Path:
    return root / ".agora" / "ai-sdlc" / "baselines" / f"{work}.json"


def capture_local_baseline(root: Path, work: str) -> Path:
    root = root.resolve()
    path = _baseline_path(root, work)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": _BASELINE_SCHEMA,
        "work": work,
        "files": _project_files(root),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_baseline(root: Path, work: str) -> dict[str, str]:
    path = _baseline_path(root, work)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict):
        return {}
    return {str(key): str(value) for key, value in files.items()}


def local_artifacts_delivery_enabled(root: Path) -> bool:
    config = root / "ai-sdlc" / "project.yaml"
    if not config.is_file():
        return False
    try:
        payload = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    target = payload.get("delivery_target")
    if isinstance(target, dict):
        return str(target.get("type") or "").strip().casefold() == "local-artifacts"
    return str(target or "").strip().casefold() == "local-artifacts"


def _governance_files(root: Path, work: str) -> tuple[str, ...]:
    candidates = (
        root / ".agora" / "intents" / work,
        root / ".agora" / "ai-sdlc" / "handoffs" / work,
        root / ".agora" / "ai-sdlc" / "verification" / work,
        root / ".agora" / "ai-sdlc" / "wizard" / work,
    )
    values: list[str] = []
    for candidate in candidates:
        if not candidate.exists():
            continue
        for path in sorted(candidate.rglob("*")):
            if path.is_file():
                values.append(path.relative_to(root).as_posix())
    return tuple(dict.fromkeys(values))


def publish_local_artifacts(
    root: Path,
    decision,
    *,
    workspace_factory=AgoraWorkspace,
) -> LocalArtifactDelivery:
    root = root.resolve()
    baseline = _read_baseline(root, decision.work)
    current = _project_files(root)
    changed = tuple(
        path for path, digest in current.items()
        if baseline.get(path) != digest
    )

    output_root = root / "output" / decision.work
    product_root = output_root / "product"
    if output_root.exists():
        shutil.rmtree(output_root)
    product_root.mkdir(parents=True, exist_ok=True)

    for relative in changed:
        source = root / relative
        destination = product_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    governance = _governance_files(root, decision.work)
    manifest = output_root / "MANIFEST.md"
    lines = [
        "# Agora Flow local delivery",
        "",
        f"- Work: {decision.swarm}/{decision.work}",
        "- Delivery target: local-artifacts",
        "",
        "## Product files generated or changed",
        "",
        *([f"- product/{item}" for item in changed] or ["- none"]),
        "",
        "## AI-SDLC artifacts",
        "",
        *([f"- {item}" for item in governance] or ["- none"]),
        "",
        "## Verification",
        "",
        "- Delivery was published only after Agora Core reached the verified criterion boundary.",
        "",
    ]
    manifest.write_text("\n".join(lines), encoding="utf-8")

    workspace = workspace_factory(cwd=root)
    actor = decision.developer_actor
    if not actor or decision.developer_actor_kind != "ai-agent":
        raise ValueError("Local artifact delivery requires the assigned AI developer actor")

    workspace.add_evidence(
        AddEvidenceInput(
            swarm_id=decision.swarm,
            work_id=decision.work,
            actor_id=actor,
            type="deployment",
            result="success",
            artifact_refs=[f"file://{manifest}"],
            environment="local-artifacts",
            dedupe_key=f"local-artifacts:{decision.work}",
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

    return LocalArtifactDelivery(
        manifest_path=str(manifest),
        output_path=str(output_root),
        product_files=changed,
        governance_files=governance,
    )
