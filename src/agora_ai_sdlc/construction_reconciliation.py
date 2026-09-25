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


@dataclass(frozen=True)
class ConstructionScaffoldResult:
    generated_artifacts: tuple[str, ...]
    registered_artifacts: tuple[str, ...]
    criterion_stages: tuple[str, ...]
    task_path: str


def construction_artifact_root(root: Path, work: str) -> Path:
    return root.resolve() / ".agora" / "ai-sdlc" / "construction" / work


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_uri(root: Path, path: Path) -> str:
    return f"repo://{path.resolve().relative_to(root.resolve()).as_posix()}"


def _artifact_text(root: Path, records: list, kind: str) -> str:
    record = next((item for item in records if item.kind == kind), None)
    if record is None:
        return ""
    uri = str(record.uri)
    if not uri.startswith("repo://"):
        return ""
    path = root / uri.removeprefix("repo://")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _scaffold_document(title: str, sources: tuple[tuple[str, str], ...]) -> str:
    lines = [
        "<!-- agora-ai-sdlc:deterministic-construction/v1 -->",
        "",
        f"# {title}",
        "",
        "This proposal is derived only from already approved Inception artifacts.",
        "It is non-authoritative implementation guidance; Agora Flow retains the governed source artifacts below.",
        "",
    ]
    for label, content in sources:
        lines.extend([f"## {label}", "", content or "_No approved source artifact content was available._", ""])
    return "\n".join(lines).rstrip() + "\n"


def prepare_construction_scaffold(
    root: Path,
    decision: GuidedDecision,
    *,
    workspace_factory=AgoraWorkspace,
) -> ConstructionScaffoldResult:
    """Materialize governance artifacts from approved Inception before invoking a coding agent."""

    if decision.state != "construction":
        raise ValueError("Construction scaffold requires Work state 'construction'")

    root = root.resolve()
    workspace = workspace_factory(cwd=root)
    actor = (decision.developer_actor or decision.actor or "").strip()
    if not actor:
        raise ValueError("Construction scaffold requires the assigned developer actor")

    records = list(workspace.list_work_artifacts(decision.swarm, decision.work))
    existing = {record.kind for record in records}
    target = construction_artifact_root(root, decision.work)
    target.mkdir(parents=True, exist_ok=True)

    source = {
        kind: _artifact_text(root, records, kind)
        for kind in (
            "intent",
            "plan",
            "requirements",
            "user-stories",
            "nfr",
            "risk-register",
            "measurement-criteria",
            "unit-of-work",
            "bolt-plan",
        )
    }
    documents = {
        "domain-model": _scaffold_document(
            "Domain Model",
            (
                ("Intent", source["intent"]),
                ("Requirements", source["requirements"]),
                ("User Stories", source["user-stories"]),
            ),
        ),
        "logical-design": _scaffold_document(
            "Logical Design",
            (
                ("Level 1 Plan", source["plan"]),
                ("NFR", source["nfr"]),
                ("Unit of Work", source["unit-of-work"]),
            ),
        ),
        "implementation-plan": _scaffold_document(
            "Implementation Plan",
            (
                ("Level 1 Plan", source["plan"]),
                ("Bolt Plan", source["bolt-plan"]),
                ("Risk Register", source["risk-register"]),
            ),
        ),
        "test-strategy": _scaffold_document(
            "Test Strategy",
            (
                ("Measurement Criteria", source["measurement-criteria"]),
                ("User Stories / Acceptance", source["user-stories"]),
                ("NFR", source["nfr"]),
            ),
        ),
        "deployment-unit": _scaffold_document(
            "Deployment Unit",
            (
                ("Unit of Work", source["unit-of-work"]),
                ("NFR", source["nfr"]),
                ("Risk Register", source["risk-register"]),
            ),
        ),
    }

    generated: list[str] = []
    registered: list[str] = []
    for kind, filename in CONSTRUCTION_ARTIFACTS:
        path = target / filename
        if kind not in existing:
            if not path.exists():
                path.write_text(documents[kind], encoding="utf-8")
                generated.append(kind)
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

    task = target / "CONSTRUCTION-TASK.md"
    task.write_text(
        "\n".join(
            [
                "# Construction Task",
                "",
                f"- Work: {decision.swarm}/{decision.work}",
                "",
                "## Executor responsibility",
                "",
                "- Create the actual product implementation outside .agora/.",
                "- Create executable automated tests outside .agora/.",
                "- For a new product, create the minimal idiomatic build/test manifest or configuration required to run those tests.",
                "- Do not merely explain or propose code in chat; persist the files in this project.",
                "- Do not mutate Agora Core. Agora Flow registers governance artifacts, evidence and criterion stages.",
                "",
                "## Governed inputs",
                "",
                "- DOMAIN-MODEL.md",
                "- LOGICAL-DESIGN.md",
                "- IMPLEMENTATION-PLAN.md",
                "- TEST-STRATEGY.md",
                "- DEPLOYMENT-UNIT.md",
                "",
                "## Success boundary",
                "",
                "The executor must leave at least one product source file and at least one automated test file.",
                "Agora Flow will execute deterministic verification after the executor exits.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    stages: list[str] = []
    if _all_construction_artifacts_present(workspace, decision) and _record_stage(
        workspace, decision, actor, "designed"
    ):
        stages.append("designed")

    return ConstructionScaffoldResult(
        generated_artifacts=tuple(generated),
        registered_artifacts=tuple(registered),
        criterion_stages=tuple(stages),
        task_path=str(task),
    )


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
    return any(Path(path).suffix.casefold() in _SOURCE_SUFFIXES and not _is_test_path(path) for path in paths)


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


def _register_support_artifact(
    root: Path,
    decision: GuidedDecision,
    workspace,
    actor: str,
    *,
    kind: str,
    path: Path,
) -> str:
    existing = workspace.list_work_artifacts(decision.swarm, decision.work)
    record = next((item for item in existing if item.kind == kind), None)
    if record is not None:
        return record.uri
    uri = _repo_uri(root, path)
    workspace.add_artifact(
        AddArtifactInput(
            swarm_id=decision.swarm,
            work_id=decision.work,
            actor_id=actor,
            kind=kind,
            uri=uri,
            content_sha256=_sha256(path),
        )
    )
    return uri


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
            report_uri = _register_support_artifact(
                root,
                decision,
                workspace,
                actor,
                kind="test-report",
                path=Path(report.report_path),
            )
            workspace.add_evidence(
                AddEvidenceInput(
                    swarm_id=decision.swarm,
                    work_id=decision.work,
                    actor_id=actor,
                    type="test-suite",
                    result="success",
                    artifact_refs=[report_uri],
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
