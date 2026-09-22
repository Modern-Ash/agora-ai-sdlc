"""Read-only, bounded AI-SDLC observations over public Core APIs.

No runner, provider SDK, network client, or lifecycle-record parser belongs here.
A snapshot is an observation, never an execution authorization.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agora.application import ActivityFilters, AgoraReadService
from agora.application.errors import AgoraApplicationError
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.observation_ui import safe_text

SCHEMA = "agora-ai-sdlc/observation/v1"
MAX_ITEMS = 50
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_DIMENSION = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")
_READ_ERRORS = (AgoraApplicationError, OSError, ValueError, RuntimeError)


def _number(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _labels(values: Any, limit: int) -> list[str]:
    return [safe_text(item) for item in list(values or ())[:limit]]


def _error_code(error: Exception) -> str:
    # Do not serialize exception messages, paths, or arbitrary provider error attributes.
    if isinstance(error, FileNotFoundError) or getattr(error, "code", None) in {
        "read.project-not-found",
        "read.resource-not-found",
        "resource.not-found",
    }:
        return "observation.resource-unavailable"
    if isinstance(error, PermissionError):
        return "observation.access-denied"
    return "observation.read-failed"


def _usage(workspace: Any, swarm: str, work: str) -> dict:
    usage = workspace.summarize_usage(swarm, work)
    dimensions = {}
    limits = usage.budget_limits or {}
    consumed = usage.consumed or {}
    for key in sorted(set(limits) | set(consumed))[:MAX_ITEMS]:
        if not isinstance(key, str) or not _DIMENSION.fullmatch(key):
            continue
        amount = _number(consumed.get(key))
        basis = (getattr(usage, "consumed_measurement", {}) or {}).get(key, "unknown")
        if basis not in {"measured", "provider-reported", "unknown"}:
            basis = "unknown"
        limit = _number(limits.get(key))
        dimensions[key] = {
            "recorded": amount,
            "measurement": basis,
            "limit": limit,
            # Absence of usage is not zero usage. Never infer a full remaining budget.
            "remaining": limit - amount if limit is not None and amount is not None else None,
        }
    return {
        "records": _number(usage.records),
        "scope": "work-records",
        "dimensions": dimensions,
        "truncated": len(set(limits) | set(consumed)) > MAX_ITEMS,
        "cost_usd": None,  # There is no normalized monetary unit in this Core usage contract.
    }


def collect(
    root: Path,
    *,
    swarm: str,
    work: str,
    limit: int = 20,
    workspace_factory=None,
    read_factory=None,
) -> dict:
    """Observe an explicit Work; never fall back to a bootstrap/other Work.

    Output is bounded; Core may enumerate its records before applying filters.
    Reads are not an atomic authority snapshot. Recheck Core before any mutation.
    """
    if not _SLUG.fullmatch(swarm) or not _SLUG.fullmatch(work):
        raise ValueError("observation.invalid-scope")
    if not 1 <= limit <= MAX_ITEMS:
        raise ValueError("observation.invalid-limit")
    workspace = (workspace_factory or AgoraWorkspace)(cwd=root)
    read = (read_factory or AgoraReadService)(workspace)
    snapshot: dict[str, Any] = {
        "schema": SCHEMA,
        "observed_at": datetime.now(UTC).isoformat(),
        "authority": "agora-core",
        "read_only": True,
        "consistency": "best-effort",
        "scope": {"swarm": swarm, "work": work},
        "status": "unavailable",
        "work": None,
        "gates": [],
        "transitions": [],
        "activity": [],
        "sessions": [],
        "artifacts": [],
        "usage": {"records": None, "scope": "work-records", "dimensions": {}, "truncated": False, "cost_usd": None},
        "warnings": [],
        "truncated": [],
        "next_action": "inspect-core-state",
    }
    try:
        record = workspace.show_work(swarm, work)
        if record.id != work or record.swarm_id != swarm:
            raise ValueError("observation.scope-mismatch")
        lifecycle = read.lifecycle(swarm, work)
        if lifecycle.work_id != work or lifecycle.swarm_id != swarm:
            raise ValueError("observation.scope-mismatch")
        snapshot["work"] = {
            "title": safe_text(record.title),
            "revision": _number(record.revision),
            "method": safe_text(lifecycle.method),
            "state": safe_text(lifecycle.current_state),
            "operational_status": safe_text(lifecycle.operational_status),
            "terminal_state": safe_text(lifecycle.terminal_state),
            # A Swarm branch is not proof of a per-Work binding.
            "branch": safe_text(getattr(record, "branch", None)),
            "base_branch": safe_text(getattr(record, "base_branch", None)),
            "branch_basis": "work-record" if getattr(record, "branch", None) else "unavailable",
            "criteria_count": len(record.acceptance_criteria),
            "satisfied_criteria_count": len(record.satisfied_criteria),
            "approval_roles": _labels(record.approval_roles, limit),
        }
        if record.state != lifecycle.current_state:
            snapshot["warnings"].append("observation.state-changed-during-read")
        current = [t for t in lifecycle.transitions if t.source == lifecycle.current_state]
        gate_ids = {t.gate_id for t in current if t.gate_id}
        gates = [g for g in lifecycle.gates if g.id in gate_ids]
        for gate in gates[:limit]:
            blockers = list(gate.blockers or ())
            snapshot["gates"].append(
                {
                    "id": safe_text(gate.id),
                    "satisfied": gate.satisfied if isinstance(gate.satisfied, bool) else None,
                    "approval_roles": _labels(gate.required_approval_roles, limit),
                    "artifact_kinds": _labels(gate.required_artifacts, limit),
                    "evidence_types": _labels(gate.required_evidence_types, limit),
                    "blockers": [
                        {
                            "code": safe_text(b.code),
                            "category": safe_text(b.category),
                            # Raw blocker messages can embed user content; only codes and references travel.
                            "references": _labels(b.references, limit),
                            "references_truncated": len(b.references or ()) > limit,
                        }
                        for b in blockers[:limit]
                    ],
                    "blocker_count": len(blockers),
                    "truncated": any(len(b.references or ()) > limit for b in blockers)
                    or any(
                        len(items or ()) > limit
                        for items in (
                            blockers,
                            gate.required_approval_roles,
                            gate.required_artifacts,
                            gate.required_evidence_types,
                        )
                    ),
                }
            )
        snapshot["transitions"] = [
            {
                "source": safe_text(t.source),
                "target": safe_text(t.target),
                "gate": safe_text(t.gate_id),
                "available": t.available if isinstance(t.available, bool) else None,
                "roles": _labels(t.authorized_roles, limit),
            }
            for t in current[:limit]
        ]
        if len(gates) > limit or len(current) > limit or any(g["truncated"] for g in snapshot["gates"]):
            snapshot["truncated"].append("governance")
        snapshot["status"] = "observed"
        # Readiness belongs to Core; a viewer does not grant a role permission to transition.
        snapshot["next_action"] = (
            "review-delivery"
            if record.state == lifecycle.terminal_state
            else "review-core-transition"
            if any(t.available is True for t in current)
            else "resolve-core-obligations"
        )
    except _READ_ERRORS as error:
        snapshot["work"] = None
        snapshot["gates"] = []
        snapshot["transitions"] = []
        snapshot["warnings"].append(_error_code(error))
        return snapshot

    def optional(name: str, operation) -> None:
        try:
            operation()
        except _READ_ERRORS:
            snapshot["warnings"].append(f"observation.{name}-unavailable")
            snapshot["status"] = "partial"

    def activity() -> None:
        entries = read.activity(ActivityFilters(swarm_id=swarm, work_id=work, limit=limit + 1))
        entries = [e for e in entries if e.swarm_id == swarm and e.work_id == work]
        snapshot["activity"] = [
            {
                "timestamp": safe_text(e.timestamp),
                "type": safe_text(e.type),
                "actor": safe_text(e.actor),
                "session": safe_text(e.session_id),
                "tool_run": safe_text(e.tool_run_id),
            }
            for e in entries[:limit]
        ]
        if len(entries) > limit:
            snapshot["truncated"].append("activity")

    def sessions() -> None:
        entries = [s for s in read.list_sessions() if s.swarm_id == swarm and s.work_id == work]
        entries.sort(key=lambda s: (s.created_at, s.id), reverse=True)
        for session in entries[:limit]:
            provenance = getattr(session, "provenance", None)
            bases = {}
            for key in ("runtime", "provider", "model"):
                value = getattr(provenance, f"{key}_basis", "unavailable")
                bases[key] = value if value in {"observed", "declared", "unavailable"} else "unavailable"
            snapshot["sessions"].append(
                {
                    "id": safe_text(session.id),
                    "status": safe_text(session.status),
                    "actor": safe_text(session.actor),
                    "executor": safe_text(session.executor),
                    "integration": safe_text(session.integration),
                    "provider": safe_text(session.provider),
                    "model": safe_text(session.model),
                    "basis": bases,
                    "created_at": safe_text(session.created_at),
                    "exit_code": session.exit_code
                    if isinstance(session.exit_code, int) and not isinstance(session.exit_code, bool)
                    else None,
                    "timeout_seconds": _number(session.timeout_seconds),
                    "output_bytes": _number(session.output_bytes),
                    "context_sha256": safe_text(session.context_sha256),
                    "runtime_version": safe_text(getattr(provenance, "runtime_version", None)),
                    "fallback_used": getattr(provenance, "fallback_used", None)
                    if isinstance(getattr(provenance, "fallback_used", None), bool)
                    else None,
                    "execution_profile": safe_text(session.execution_profile),
                }
            )
        if len(entries) > limit:
            snapshot["truncated"].append("sessions")

    def artifacts() -> None:
        entries = read.artifacts(swarm, work)
        snapshot["artifacts"] = [
            {
                "kind": safe_text(a.kind),
                "uri": safe_text(a.uri),
                "sha256": safe_text(a.content_sha256),
                "produced_by": safe_text(a.produced_by),
                "timestamp": safe_text(a.timestamp),
            }
            for a in entries[:limit]
        ]
        if len(entries) > limit:
            snapshot["truncated"].append("artifacts")

    def usage() -> None:
        snapshot["usage"] = _usage(workspace, swarm, work)

    optional("activity", activity)
    optional("sessions", sessions)
    optional("artifacts", artifacts)
    optional("usage", usage)
    try:
        current_record = workspace.show_work(swarm, work)
        if (current_record.revision, current_record.state, current_record.operational_status) != (
            record.revision,
            record.state,
            record.operational_status,
        ):
            snapshot["warnings"].append("observation.state-changed-during-read")
    except _READ_ERRORS:
        snapshot["warnings"].append("observation.state-recheck-unavailable")
    if snapshot["warnings"]:
        snapshot["status"] = "partial"
    if "governance" in snapshot["truncated"] or any("state-" in w for w in snapshot["warnings"]):
        snapshot["next_action"] = "inspect-core-state"
    return snapshot


def agent_summary(snapshot: dict) -> dict:
    """Stable compact contract. UI detail, locale, activity and heartbeat never enter it."""
    return {
        "schema": "agora-ai-sdlc/observation-summary/v1",
        "authority": snapshot["authority"],
        "read_only": True,
        "consistency": snapshot["consistency"],
        "scope": snapshot["scope"],
        "status": snapshot["status"],
        "work": snapshot["work"],
        "gates": snapshot["gates"],
        "transitions": snapshot["transitions"],
        "latest_session": snapshot["sessions"][0] if snapshot["sessions"] else None,
        "usage": snapshot["usage"],
        "warnings": snapshot["warnings"],
        "truncated": snapshot["truncated"],
        "next_action": snapshot["next_action"],
    }
