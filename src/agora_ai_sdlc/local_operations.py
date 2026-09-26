"""Deterministic Operations preparation for local-artifacts delivery."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from agora.model import AddArtifactInput, AddEvidenceInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.local_delivery import changed_product_files

_FORBIDDEN_SECURITY_PATTERNS = (
    ("dynamic-eval", ("eval(", "new Function(", "Function(")),
    ("process-spawn", ("child_process", "exec(", "spawn(")),
    ("network-access", ("fetch(", "http://", "https://", "XMLHttpRequest")),
)
# Lockfiles are generated dependency metadata (registry URLs, integrity hashes),
# not product code, so pattern matching them only yields false positives.
_SECURITY_SCAN_EXEMPT_FILES = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "uv.lock",
        "poetry.lock",
        "cargo.lock",
        "go.sum",
    }
)
_OPERATION_ARTIFACTS = (
    ("operational-readiness", "OPERATIONAL-READINESS.md"),
    ("rollback-procedure", "ROLLBACK-PROCEDURE.md"),
)


@dataclass(frozen=True)
class LocalOperationsPreparation:
    registered_artifacts: tuple[str, ...]
    security_scan_path: str
    findings: tuple[str, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_uri(root: Path, path: Path) -> str:
    return f"repo://{path.resolve().relative_to(root.resolve()).as_posix()}"


def _scan_local_product(root: Path, work: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    paths = changed_product_files(root, work)
    findings: list[str] = []
    for relative in paths:
        path = root / relative
        if not path.is_file() or path.name.casefold() in _SECURITY_SCAN_EXEMPT_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for code, patterns in _FORBIDDEN_SECURITY_PATTERNS:
            if any(pattern in text for pattern in patterns):
                findings.append(f"{code}:{relative}")
    return paths, tuple(dict.fromkeys(findings))


def prepare_local_operations(
    root: Path,
    decision: GuidedDecision,
    *,
    workspace_factory=AgoraWorkspace,
) -> LocalOperationsPreparation:
    """Prepare local delivery artifacts and deterministic security evidence."""

    if decision.state != "operations":
        raise ValueError("local Operations preparation requires Work state 'operations'")

    root = root.resolve()
    workspace = workspace_factory(cwd=root)
    actor = (decision.developer_actor or decision.actor or "").strip()
    if not actor:
        raise ValueError("local Operations preparation requires the assigned developer actor")

    changed, findings = _scan_local_product(root, decision.work)
    if findings:
        raise ValueError("local security scan reported findings: " + ", ".join(findings))

    target = root / ".agora" / "ai-sdlc" / "operations" / decision.work
    target.mkdir(parents=True, exist_ok=True)

    documents = {
        "operational-readiness": "\n".join(
            [
                "# Operational Readiness",
                "",
                f"- Work: {decision.swarm}/{decision.work}",
                "- Delivery target: local-artifacts",
                f"- Product files: {len(changed)}",
                "- Verification boundary: Construction criteria were verified before Operations.",
                "- Runtime dependencies: local filesystem only; no remote deployment is performed.",
                "",
                "## Readiness decision",
                "",
                "- Ready to publish the verified local artifact bundle for human review.",
            ]
        ),
        "rollback-procedure": "\n".join(
            [
                "# Rollback Procedure",
                "",
                f"- Work: {decision.swarm}/{decision.work}",
                "- Delivery target: local-artifacts",
                "",
                "## Procedure",
                "",
                "- Remove the generated output/<work> directory to withdraw the local delivery.",
                "- Keep the governed .agora evidence/history intact for auditability.",
                "- Re-run Agora Flow after correcting product files or acceptance criteria.",
            ]
        ),
    }

    existing = {record.kind for record in workspace.list_work_artifacts(decision.swarm, decision.work)}
    registered: list[str] = []
    for kind, filename in _OPERATION_ARTIFACTS:
        path = target / filename
        if kind not in existing:
            path.write_text(documents[kind].rstrip() + "\n", encoding="utf-8")
            workspace.add_artifact(
                AddArtifactInput(
                    swarm_id=decision.swarm,
                    work_id=decision.work,
                    actor_id=actor,
                    kind=kind,
                    uri=_repo_uri(root, path),
                    content_sha256=_sha256(path),
                )
            )
            registered.append(kind)

    scan_path = target / "SECURITY-SCAN.md"
    scan_path.write_text(
        "\n".join(
            [
                "# Local Security Scan",
                "",
                f"- Work: {decision.swarm}/{decision.work}",
                f"- Files scanned: {len(changed)}",
                "- Result: success",
                "",
                "## Checks",
                "",
                "- dynamic eval/function construction",
                "- process spawning",
                "- external/network access",
                "",
                "## Findings",
                "",
                "- none",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    existing = workspace.list_work_artifacts(decision.swarm, decision.work)
    scan_record = next((item for item in existing if item.kind == "security-scan-report"), None)
    if scan_record is None:
        scan_uri = _repo_uri(root, scan_path)
        workspace.add_artifact(
            AddArtifactInput(
                swarm_id=decision.swarm,
                work_id=decision.work,
                actor_id=actor,
                kind="security-scan-report",
                uri=scan_uri,
                content_sha256=_sha256(scan_path),
            )
        )
    else:
        scan_uri = scan_record.uri

    workspace.add_evidence(
        AddEvidenceInput(
            swarm_id=decision.swarm,
            work_id=decision.work,
            actor_id=actor,
            type="security-scan",
            result="success",
            artifact_refs=[scan_uri],
            environment="local-artifacts",
            dedupe_key=f"security-scan:{decision.work}",
        )
    )

    return LocalOperationsPreparation(
        registered_artifacts=tuple(registered),
        security_scan_path=str(scan_path),
        findings=findings,
    )
