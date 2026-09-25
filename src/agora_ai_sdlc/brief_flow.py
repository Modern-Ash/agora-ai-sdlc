"""Start Agora AI-SDLC from a local Intent Brief without Git or an issue tracker."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from agora.model import CreateIntentInput, CreateWorkInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.deterministic_clarification import record_zero_question_clarification
from agora_ai_sdlc.deterministic_inception import build_deterministic_inception
from agora_ai_sdlc.inception_handoff import write_inception_handoff
from agora_ai_sdlc.inception_materialization import (
    materialize_deterministic_inception,
    materialize_deterministic_inception_outputs,
)
from agora_ai_sdlc.local_delivery import capture_local_baseline
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.start_flow import StartFlowError, _select_runtime
from agora_ai_sdlc.start_preflight import StartPreparationResult, ensure_start_ready


@dataclass(frozen=True)
class BriefStartResult:
    source_kind: str
    source_ref: str
    source_title: str
    intent_id: str
    intent_path: str
    swarm_id: str
    work_id: str
    work_path: str
    runtime_id: str
    runtime_name: str
    runtime_model: str | None
    workspace_root: str
    deterministic_inception_path: str
    handoff_path: str
    baseline_path: str
    output_path: str
    preflight_actions: tuple[str, ...]
    status: str = "human-review-required"

    def snapshot(self) -> dict:
        return asdict(self)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "brief"


def _brief_payload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    title = ""
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            title = match.group(1).strip()
            break
    if not title:
        title = path.stem.replace("_", " ").replace("-", " ").strip().title() or "Intent Brief"
    return {"title": title, "body": text}


def _ensure_brief_work(
    workspace: AgoraWorkspace,
    *,
    swarm_id: str,
    work_id: str,
    actor_id: str,
    title: str,
    source_ref: str,
):
    existing = next((item for item in workspace.list_work(swarm_id=swarm_id) if item.id == work_id), None)
    if existing is not None:
        return existing
    return workspace.create_work(
        CreateWorkInput(
            swarm_id=swarm_id,
            id=work_id,
            title=f"Deliver Intent Brief: {title}",
            actor_id=actor_id,
            acceptance_criteria=[("source-issue", "Satisfy the acceptance criteria declared by the Intent Brief")],
            description=f"Source brief: {source_ref}",
        )
    )


def prepare_brief_start(
    root: Path,
    *,
    brief: Path,
    agent: str | None = None,
    model: str | None = None,
    swarm: str = "delivery",
    actor: str = "product-owner",
    workspace_factory=AgoraWorkspace,
    runtime_discovery=discover_runtimes,
    preflight=ensure_start_ready,
) -> BriefStartResult:
    """Create/reuse one governed Work from a local Intent Brief."""

    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    brief = brief.expanduser()
    if not brief.is_absolute():
        brief = (root / brief).resolve()
    if not brief.is_file():
        raise StartFlowError(f"Intent Brief does not exist: {brief}")

    payload = _brief_payload(brief)
    title = str(payload["title"])
    work_id = _slug(title)
    intent_id = work_id
    source_ref = brief.as_uri()

    runtime: RuntimeDiscovery = _select_runtime(root, agent, discovery=runtime_discovery)
    if model and runtime.id != "opencode":
        raise StartFlowError("Explicit --model selection is currently supported only with --agent opencode")

    prepared: StartPreparationResult = preflight(
        root,
        runtime,
        swarm_id=swarm,
        work_key=work_id,
        require_git=False,
        integrations=(),
        delivery_target="local-artifacts",
        pathway="new-product",
        workspace_factory=workspace_factory,
    )
    root = prepared.root
    resolved_swarm = prepared.swarm_id or swarm
    workspace = workspace_factory(cwd=root)

    work_record = _ensure_brief_work(
        workspace,
        swarm_id=resolved_swarm,
        work_id=work_id,
        actor_id=actor,
        title=title,
        source_ref=source_ref,
    )

    try:
        intent = workspace.get_intent(intent_id)
    except (AttributeError, FileNotFoundError):
        intent = workspace.create_intent(
            CreateIntentInput(
                id=intent_id,
                author=f"project:{actor}",
                problem=title,
                outcome=f"Deliver the outcome described by the Intent Brief: {title}",
                affected_systems=[root.name],
                constraints=[],
                open_questions=[],
                source=source_ref,
            )
        )

    deterministic = build_deterministic_inception(
        root,
        payload,
        intent_id=intent.id,
        work_id=work_record.id,
        pathway="new-product",
    )
    deterministic_relative = Path(deterministic.path).relative_to(root).as_posix()
    handoff = write_inception_handoff(
        root,
        intent_id=intent.id,
        issue_url=source_ref,
        issue_title=title,
        runtime_id=runtime.id,
        runtime_name=runtime.name,
        swarm_id=resolved_swarm,
        work_id=work_record.id,
        branch=None,
        base_branch=None,
        pathway="new-product",
        deterministic_draft=deterministic_relative,
        semantic_gaps=deterministic.semantic_gaps,
    )

    materialized = materialize_deterministic_inception(
        root,
        workspace=workspace,
        swarm_id=resolved_swarm,
        work_id=work_record.id,
        intent_path=intent.path,
        issue=deterministic.issue,
        pathway="new-product",
    )
    deterministic_output_actions: tuple[str, ...] = ()
    clarification_actions: tuple[str, ...] = ()
    if not deterministic.semantic_gaps:
        deterministic_output_actions = materialize_deterministic_inception_outputs(
            root,
            workspace=workspace,
            swarm_id=resolved_swarm,
            work_id=work_record.id,
            actor_id=materialized.actor_id,
            intent_path=intent.path,
            deterministic_output=deterministic.output,
        )
        clarification = record_zero_question_clarification(
            workspace=workspace,
            swarm_id=resolved_swarm,
            work_id=work_record.id,
            actor_id=materialized.actor_id,
        )
        clarification_actions = tuple(getattr(clarification, "actions", ()) or ())

    baseline = capture_local_baseline(root, work_record.id)
    output_path = root / "output" / work_record.id

    return BriefStartResult(
        source_kind="intent-brief",
        source_ref=source_ref,
        source_title=title,
        intent_id=intent.id,
        intent_path=intent.path,
        swarm_id=resolved_swarm,
        work_id=work_record.id,
        work_path=work_record.path,
        runtime_id=runtime.id,
        runtime_name=runtime.name,
        runtime_model=model,
        workspace_root=str(root),
        deterministic_inception_path=deterministic.path,
        handoff_path=handoff.path,
        baseline_path=str(baseline),
        output_path=str(output_path),
        preflight_actions=tuple(prepared.actions)
        + tuple(getattr(materialized, "actions", ()) or ())
        + deterministic_output_actions
        + clarification_actions,
    )


def render_brief_start(result: BriefStartResult, *, lang: str = "en") -> str:
    es = lang == "es"
    lines = [
        "Agora Flow | Brief",
        "",
        f"Brief: {result.source_title}",
        f"✓ {'Fuente' if es else 'Source'}: {result.source_ref}",
        f"✓ {'Work gobernado' if es else 'Governed Work'}: {result.swarm_id}/{result.work_id}",
        f"✓ {'IA seleccionada' if es else 'Selected AI'}: {result.runtime_name}",
        "✓ Delivery target: local-artifacts",
        f"✓ {'Salida final' if es else 'Final output'}: {result.output_path}",
        "",
        "INCEPTION",
        f"✓ {'Draft determinístico' if es else 'Deterministic draft'}: {result.deterministic_inception_path}",
        f"✓ Handoff: {result.handoff_path}",
        "",
        (
            "Revisá y aprobá la propuesta de Inception; después Agora Flow continuará con Construction."
            if es
            else "Review and approve the Inception proposal; Agora Flow will then continue with Construction."
        ),
    ]
    return "\n".join(lines)
