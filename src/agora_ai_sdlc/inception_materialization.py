"""Materialize deterministic Inception facts into Agora Core without fabricating approvals."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from agora.model import AddArtifactInput, WorkActorInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.deterministic_inception import IssueFacts

GENERATED_MARKER = "<!-- agora-ai-sdlc:deterministic-inception/v1 -->"


class InceptionMaterializationError(ValueError):
    """Deterministic Inception cannot be materialized safely."""


@dataclass(frozen=True)
class InceptionMaterializationResult:
    actor_id: str
    intent_uri: str
    requirements_uri: str
    unit_of_work_uri: str
    actions: tuple[str, ...]


def _repo_uri(root: Path, path: Path) -> str:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        relative = resolved_path.relative_to(resolved_root)
    except ValueError as error:
        raise InceptionMaterializationError(f"artifact path escapes project root: {path}") from error
    return f"repo://{relative.as_posix()}"


def _write_generated(path: Path, content: str) -> bool:
    payload = f"{GENERATED_MARKER}\n\n{content.rstrip()}\n"
    if path.is_file():
        current = path.read_text(encoding="utf-8")
        if current == payload:
            return False
        if not current.startswith(GENERATED_MARKER):
            raise InceptionMaterializationError(f"refusing to overwrite non-generated Inception artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return True


def _bullets(values: tuple[str, ...], fallback: str) -> list[str]:
    return [f"- {item}" for item in values] if values else [f"- {fallback}"]


def _requirements_document(issue: IssueFacts) -> str:
    return "\n".join(
        [
            "# Deterministic Requirements",
            "",
            "## Objective",
            "",
            issue.objective,
            "",
            "## Requirements",
            "",
            *_bullets(
                issue.requirements,
                "No separate requirements section; acceptance criteria remain authoritative.",
            ),
            "",
            "## Acceptance criteria",
            "",
            *_bullets(issue.acceptance_criteria, "No explicit acceptance criteria."),
            "",
            "## Constraints",
            "",
            *_bullets(issue.constraints, "No explicit constraints."),
            "",
            "## Dependencies",
            "",
            *_bullets(issue.dependencies, "No explicit dependencies."),
        ]
    )


def _unit_of_work_document(issue: IssueFacts, *, work_id: str, pathway: str) -> str:
    return "\n".join(
        [
            "# Deterministic Unit of Work",
            "",
            f"- Work: {work_id}",
            f"- Pathway: {pathway}",
            "",
            "## Objective",
            "",
            issue.objective,
            "",
            "## Scope",
            "",
            "- Deliver the explicit source-issue objective within the governed Work.",
            "- Preserve the source constraints and acceptance criteria without widening scope.",
            "",
            "## Acceptance criteria",
            "",
            *_bullets(issue.acceptance_criteria, "No explicit acceptance criteria."),
            "",
            "## Constraints",
            "",
            *_bullets(issue.constraints, "No explicit constraints."),
            "",
            "## Dependencies",
            "",
            *_bullets(issue.dependencies, "No explicit dependencies."),
        ]
    )


def _content_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ensure_artifact(
    workspace: AgoraWorkspace,
    *,
    root: Path,
    swarm_id: str,
    work_id: str,
    actor_id: str,
    kind: str,
    path: Path,
    actions: list[str],
) -> None:
    uri = _repo_uri(root, path)
    digest = _content_sha256(path)
    existing = workspace.list_work_artifacts(swarm_id, work_id)

    if any(record.kind == kind and record.uri == uri and record.content_sha256 == digest for record in existing):
        return
    if any(record.kind == kind for record in existing):
        actions.append(f"artifact.existing:{kind}")
        return

    workspace.add_artifact(
        AddArtifactInput(
            swarm_id=swarm_id,
            work_id=work_id,
            actor_id=actor_id,
            kind=kind,
            uri=uri,
            content_sha256=digest,
        )
    )
    actions.append(f"artifact.registered:{kind}")


def materialize_deterministic_inception(
    root: Path,
    *,
    workspace: AgoraWorkspace,
    swarm_id: str,
    work_id: str,
    intent_path: str,
    issue: IssueFacts,
    pathway: str,
) -> InceptionMaterializationResult:
    """Materialize only deterministic facts; human approvals remain untouched."""

    root = root.resolve()
    swarm = workspace.show_swarm(swarm_id)
    actor_id = swarm.assignments.get("developer")
    if not actor_id:
        raise InceptionMaterializationError(
            f"developer actor is not assigned in swarm {swarm_id!r}; cannot materialize Inception"
        )

    intent = Path(intent_path)
    if not intent.is_absolute():
        intent = root / intent
    intent = intent.resolve()
    if not intent.is_file():
        raise InceptionMaterializationError(f"durable Intent file does not exist: {intent}")

    intent_dir = intent.parent
    requirements = intent_dir / "REQUIREMENTS.md"
    unit_of_work = intent_dir / "UNIT-OF-WORK.md"

    actions: list[str] = []
    existing = workspace.list_work_artifacts(swarm_id, work_id)
    existing_by_kind = {record.kind: record for record in existing}

    if "requirements" not in existing_by_kind and _write_generated(
        requirements,
        _requirements_document(issue),
    ):
        actions.append("artifact.generated:requirements")
    if "unit-of-work" not in existing_by_kind and _write_generated(
        unit_of_work,
        _unit_of_work_document(issue, work_id=work_id, pathway=pathway),
    ):
        actions.append("artifact.generated:unit-of-work")

    if "intent" not in existing_by_kind:
        _ensure_artifact(
            workspace,
            root=root,
            swarm_id=swarm_id,
            work_id=work_id,
            actor_id=actor_id,
            kind="intent",
            path=intent,
            actions=actions,
        )
    if "requirements" not in existing_by_kind:
        _ensure_artifact(
            workspace,
            root=root,
            swarm_id=swarm_id,
            work_id=work_id,
            actor_id=actor_id,
            kind="requirements",
            path=requirements,
            actions=actions,
        )
    if "unit-of-work" not in existing_by_kind:
        _ensure_artifact(
            workspace,
            root=root,
            swarm_id=swarm_id,
            work_id=work_id,
            actor_id=actor_id,
            kind="unit-of-work",
            path=unit_of_work,
            actions=actions,
        )

    work = workspace.show_work(swarm_id, work_id)
    if "source-issue" not in work.acceptance_criteria:
        raise InceptionMaterializationError(f"Work {work_id!r} has no source-issue acceptance criterion to elaborate")
    stages = work.criterion_statuses.get("source-issue", [])
    if "elaborated" not in stages:
        workspace.satisfy_criterion(
            WorkActorInput(
                swarm_id=swarm_id,
                work_id=work_id,
                actor_id=actor_id,
            ),
            "source-issue",
            stage="elaborated",
        )
        actions.append("criterion.elaborated:source-issue")

    final_records = workspace.list_work_artifacts(swarm_id, work_id)
    final_by_kind = {record.kind: record for record in final_records}
    missing = [kind for kind in ("intent", "requirements", "unit-of-work") if kind not in final_by_kind]
    if missing:
        raise InceptionMaterializationError(
            "deterministic Inception materialization did not register required artifacts: " + ", ".join(missing)
        )

    return InceptionMaterializationResult(
        actor_id=actor_id,
        intent_uri=final_by_kind["intent"].uri,
        requirements_uri=final_by_kind["requirements"].uri,
        unit_of_work_uri=final_by_kind["unit-of-work"].uri,
        actions=tuple(actions),
    )
