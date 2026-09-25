"""Host-owned reconciliation after one Construction executor iteration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from agora.model import AddArtifactInput, AddEvidenceInput, WorkActorInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.local_delivery import changed_product_files
from agora_ai_sdlc.verification import build_verification_report

CONSTRUCTION_ARTIFACTS = (
    ("domain-model", "DOMAIN-MODEL.md"),
    ("logical-design", "LOGICAL-DESIGN.md"),
    ("implementation-plan", "IMPLEMENTATION-PLAN.md"),
    ("test-strategy", "TEST-STRATEGY.md"),
    ("deployment-unit", "DEPLOYMENT-UNIT.md"),
)

_SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".py", ".java", ".kt", ".go", ".rs"}
_TEST_MARKERS = ("/test/", "/tests/", "/__tests__/")


@dataclass(frozen=True)
class ConstructionReconciliationResult:
    registered_artifacts: tuple[str, ...]
    changed_product_files: tuple[str, ...]
    criterion_stages: tuple[str, ...]
    verification_passed: bool
    verification_report: str | None


def construction_artifact_root(root: Path, work: str) -> Path:
    return root.resolve() / ".agora" / "ai-sdlc" / "construction" / work


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_uri(root: Path, path: Path) -> str:
    return f"repo://{path.resolve().relative_to(root.resolve()).as_posix()}"


def _is_test_path(path: str) -> bool:
    lowered = "/" + path.casefold().lstrip("/")
    name = Path(path).name.casefold()
    stem = Path(path).stem.casefold()
    return (
        any(marker in lowered for marker in _TEST_MARKERS)
        or name.startswith("test_")
        or stem.endswith((".test", ".spec", "_test", "test"))
    )


def _has_product_implementation(paths: tuple[str, ...]) -> bool:
    return any(
        Path(path).suffix.casefold() in _SOURCE_SUFFIXES and not _is_test_path(path)
        for path in paths
    )


def _has_product_tests(paths: tuple[str, ...]) -> bool:
    return any(Path(path).suffix.casefold() in _SOURCE_SUFFIXES and _is_test_path(path) for path in paths)


def _register_artifacts(
    root: Path,
    decision: GuidedDecision,
    workspace,
    actor: str,
) -> tuple[str, ...]:
    target = construction_artifact_root(root, decision.work)
    existing = {record.kind for record in workspace.list_work_artifacts(decision.swarm, decision.work)}
    registered: list[str] = []

    for kind, filename in CONSTRUCTION_ARTIFACTS:
        if kind in existing:
            continue
        path = target / filename
        if not path.is_file():
            continue
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
        existing.add(kind)
    return tuple(registered)


def _record_stage(workspace, decision: GuidedDecision, actor: str, stage: str) -> bool:
    work = workspace.show_work(decision.swarm, decision.work)
    current = set((getattr(work, "criterion_statuses", {}) or {}).get("source-issue", ()))
    if stage in current:
        return False
    workspace.satisfy_criterion(
        WorkActorInput(
            swarm_id=decision.swarm,
            work_id=decision.work,
            actor_id=actor,
        ),
        "source-issue",
        stage=stage,
    )
    return True


def _all_construction_artifacts_present(workspace, decision: GuidedDecision) -> bool:
    kinds = {record.kind for record in workspace.list_work_artifacts(decision.swarm, decision.work)}
    return all(kind in kinds for kind, _ in CONSTRUCTION_ARTIFACTS)


def reconcile_construction_execution(
    root: Path,
    decision: GuidedDecision,
    *,
    workspace_factory=AgoraWorkspace,
) -> ConstructionReconciliationResult:
    """Convert observable executor outputs into authoritative Core progress.

    The executor owns generation. Agora Flow owns registration, criterion
    progression and deterministic verification. Nothing is inferred when the
    corresponding files/evidence are absent.
    """

    if decision.state != "construction":
        return ConstructionReconciliationResult((), (), (), False, None)

    root = root.resolve()
    workspace = workspace_factory(cwd=root)
    actor = (decision.developer_actor or decision.actor or "").strip()
    if not actor:
        raise ValueError("Construction reconciliation requires the assigned developer actor")

    registered = _register_artifacts(root, decision, workspace, actor)
    changed = changed_product_files(root, decision.work)
    stages: list[str] = []

    artifacts_complete = _all_construction_artifacts_present(workspace, decision)
    if artifacts_complete and _record_stage(workspace, decision, actor, "designed"):
        stages.append("designed")

    implementation_present = _has_product_implementation(changed)
    tests_present = _has_product_tests(changed)
    if artifacts_complete and implementation_present and _record_stage(workspace, decision, actor, "built"):
        stages.append("built")

    verification_passed = False
    report_path: str | None = None
    if artifacts_complete and implementation_present and tests_present:
        report = build_verification_report(
            root,
            swarm=decision.swarm,
            work=decision.work,
            run=True,
            timeout_seconds=300,
            persist=True,
        )
        report_path = report.report_path
        verification_passed = bool(
            report.commands
            and report.all_executed_commands_passed is True
            and all(command.status == "passed" for command in report.commands)
        )
        if verification_passed and report.report_path:
            workspace.add_evidence(
                AddEvidenceInput(
                    swarm_id=decision.swarm,
                    work_id=decision.work,
                    actor_id=actor,
                    type="test-suite",
                    result="success",
                    artifact_refs=[f"file://{report.report_path}"],
                    environment="local-construction",
                    dedupe_key=f"test-suite:{decision.work}",
                )
            )
            if _record_stage(workspace, decision, actor, "verified"):
                stages.append("verified")

    return ConstructionReconciliationResult(
        registered_artifacts=registered,
        changed_product_files=changed,
        criterion_stages=tuple(stages),
        verification_passed=verification_passed,
        verification_report=report_path,
    )
