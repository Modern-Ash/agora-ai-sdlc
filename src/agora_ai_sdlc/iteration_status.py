"""Low-cost human observability and compact agent context for one AI-SDLC iteration."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.guided import GuidedDecision, inspect_next
from agora_ai_sdlc.progress import lifecycle_progress


@dataclass(frozen=True)
class IterationStatus:
    swarm: str | None
    work: str | None
    title: str | None
    method: str | None
    state: str | None
    target: str | None
    gate: str | None
    actor: str | None
    role: str | None
    base_branch: str | None
    work_branch: str | None
    current_branch: str | None
    missing_artifacts: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    missing_approvals: tuple[str, ...]
    unsatisfied_criteria: tuple[str, ...]
    git_issues: tuple[str, ...]
    clarification_issues: tuple[str, ...]
    artifact_kinds: tuple[str, ...]
    evidence_results: tuple[str, ...]
    last_activity: str | None
    ready_for_human_approval: bool
    ready_to_transition: bool
    usage_status: str = "unknown"

    def snapshot(self) -> dict:
        return asdict(self)

    def agent_context(self) -> dict:
        """Bounded context for executors; excludes UI prose, logs and diagnostic narration."""

        if self.ready_for_human_approval and self.missing_approvals:
            next_action = "human-approval"
        elif any(
            (
                self.missing_artifacts,
                self.missing_evidence,
                self.unsatisfied_criteria,
                self.git_issues,
                self.clarification_issues,
            )
        ):
            next_action = "resolve-governance-obligations"
        elif self.ready_to_transition and self.target:
            next_action = "governed-transition"
        elif self.work is None:
            next_action = "no-active-work"
        else:
            next_action = "inspect-next"

        return {
            "schema": "agora-ai-sdlc/agent-context/v1",
            "iteration": {
                "swarm": self.swarm,
                "work": self.work,
                "state": self.state,
                "target": self.target,
                "base_branch": self.base_branch,
                "branch": self.work_branch or self.current_branch,
            },
            "authority": {
                "role": self.role,
                "actor": self.actor,
                "human_approval_required": bool(self.missing_approvals),
            },
            "blockers": {
                "artifacts": list(self.missing_artifacts),
                "evidence": list(self.missing_evidence),
                "approvals": list(self.missing_approvals),
                "criteria": list(self.unsatisfied_criteria),
                "git": list(self.git_issues),
                "clarifications": list(self.clarification_issues),
            },
            "references": {
                "artifact_kinds": list(self.artifact_kinds),
                "evidence_results": list(self.evidence_results),
            },
            "next_action": next_action,
        }


def _current_branch(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _last_activity(workspace: AgoraWorkspace, swarm: str, work: str) -> str | None:
    try:
        records = workspace.list_activity(swarm_id=swarm, work_id=work, limit=1)
    except (AttributeError, OSError, ValueError):
        return None
    if not records:
        return None
    record = records[-1]
    summary = str(getattr(record, "summary", "") or "").strip()
    kind = str(getattr(record, "type", "") or "").strip()
    return f"{kind}: {summary}" if kind and summary else (summary or kind or None)


def _decision_or_none(
    root: Path,
    *,
    swarm: str | None,
    work: str | None,
) -> GuidedDecision | None:
    try:
        return inspect_next(root, swarm=swarm, work=work)
    except (OSError, ValueError):
        return None


def inspect_iteration(
    root: Path,
    *,
    swarm: str | None = None,
    work: str | None = None,
) -> IterationStatus:
    """Read local/Core facts only. Rendering this status never invokes an LLM."""

    root = root.expanduser().resolve()
    workspace = AgoraWorkspace(cwd=root)
    decision = _decision_or_none(root, swarm=swarm, work=work)

    resolved_swarm = decision.swarm if decision is not None else swarm
    resolved_work = decision.work if decision is not None else work
    record = None

    if resolved_swarm and resolved_work:
        try:
            record = workspace.show_work(resolved_swarm, resolved_work)
        except (OSError, ValueError, FileNotFoundError):
            record = None
    elif resolved_swarm:
        try:
            candidates = workspace.list_work(swarm_id=resolved_swarm)
        except (OSError, ValueError):
            candidates = []
        if candidates:
            record = candidates[0]
            resolved_work = record.id
    else:
        try:
            candidates = workspace.list_work()
        except (OSError, ValueError):
            candidates = []
        if candidates:
            record = candidates[0]
            resolved_swarm = record.swarm_id
            resolved_work = record.id

    if decision is None and resolved_swarm and resolved_work:
        decision = _decision_or_none(root, swarm=resolved_swarm, work=resolved_work)

    title = decision.title if decision is not None else getattr(record, "title", None)
    state = decision.state if decision is not None else getattr(record, "state", None)
    method = decision.method if decision is not None else None

    artifact_kinds = tuple(getattr(record, "artifact_kinds", ()) or ())
    evidence_results = tuple(getattr(record, "evidence_results", ()) or ())

    return IterationStatus(
        swarm=resolved_swarm,
        work=resolved_work,
        title=title,
        method=method,
        state=state,
        target=decision.target if decision is not None else None,
        gate=decision.gate if decision is not None else None,
        actor=decision.actor if decision is not None else None,
        role=decision.role if decision is not None else None,
        base_branch=getattr(record, "base_branch", None) if record is not None else None,
        work_branch=getattr(record, "branch", None) if record is not None else None,
        current_branch=_current_branch(root),
        missing_artifacts=decision.missing_artifacts if decision is not None else (),
        missing_evidence=decision.missing_evidence if decision is not None else (),
        missing_approvals=decision.missing_approvals if decision is not None else (),
        unsatisfied_criteria=decision.unsatisfied_criteria if decision is not None else (),
        git_issues=decision.git_issues if decision is not None else (),
        clarification_issues=decision.clarification_issues if decision is not None else (),
        artifact_kinds=artifact_kinds,
        evidence_results=evidence_results,
        last_activity=(
            _last_activity(workspace, resolved_swarm, resolved_work) if resolved_swarm and resolved_work else None
        ),
        ready_for_human_approval=(decision.ready_for_human_approval if decision is not None else False),
        ready_to_transition=decision.ready_to_transition if decision is not None else False,
    )


def render_status(status: IterationStatus, *, detail: str = "normal") -> str:
    if detail not in {"normal", "detail", "diagnostic"}:
        raise ValueError(f"unsupported detail level {detail!r}")

    lines = ["Agora AI-SDLC | Iteration", ""]
    lines.append(f"Work: {status.swarm or '-'} / {status.work or '-'}")
    if status.title:
        lines.append(f"Objective: {status.title}")
    lines.append(f"Stage: {status.state or 'unknown'}" + (f" -> {status.target}" if status.target else ""))
    lines.append(f"Lifecycle: {lifecycle_progress(status.state)}")
    lines.append(
        f"Branch: {status.work_branch or status.current_branch or 'unknown'}"
        + (f" (base {status.base_branch})" if status.base_branch else "")
    )
    lines.append(f"Authority: {status.role or 'unknown'}" + (f" ({status.actor})" if status.actor else ""))
    lines.append(f"Usage: {status.usage_status}")

    obligations = (
        ("Artifacts", status.missing_artifacts),
        ("Evidence", status.missing_evidence),
        ("Approvals", status.missing_approvals),
        ("Criteria", status.unsatisfied_criteria),
        ("Git", status.git_issues),
        ("Clarifications", status.clarification_issues),
    )
    lines.extend(["", "Governance"])
    for label, pending in obligations:
        lines.append(f"  {'!' if pending else '✓'} {label}" + (f": {', '.join(pending)}" if pending else ""))

    context = status.agent_context()
    lines.extend(["", f"Next action: {context['next_action']}"])

    if detail in {"detail", "diagnostic"}:
        lines.extend(["", "Observed facts"])
        lines.append(f"  Current Git branch: {status.current_branch or 'unknown'}")
        lines.append("  Artifact kinds: " + (", ".join(status.artifact_kinds) if status.artifact_kinds else "none"))
        lines.append(
            "  Evidence results: " + (", ".join(status.evidence_results) if status.evidence_results else "none")
        )
        lines.append(f"  Last activity: {status.last_activity or 'unknown'}")

    if detail == "diagnostic":
        lines.extend(["", "Diagnostic"])
        lines.append(f"  Gate: {status.gate or 'none'}")
        lines.append(f"  Ready for human approval: {status.ready_for_human_approval}")
        lines.append(f"  Ready to transition: {status.ready_to_transition}")
        lines.append("  Rendering source: local/Core facts only; no LLM call")

    return "\n".join(lines)
