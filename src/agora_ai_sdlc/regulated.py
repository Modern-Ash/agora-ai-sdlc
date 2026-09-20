"""Fail-closed controls composed by the Regulated adoption profile.

Agora Core remains authoritative for actors, lifecycle actions, Ed25519
verification, stale preconditions, and work state. This module performs profile
preflight and stores only profile-owned audit metadata.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from agora.model import (
    ActorRecord,
    ApplyLifecycleActionInput,
    AssignActorInput,
    LifecycleActionRecord,
    PrepareEvidenceInput,
    PrepareWorkTransitionInput,
    SwarmRecord,
)

from agora_ai_sdlc.provenance import FIELDS, RANK, Provenance

SCHEMA = "agora-ai-sdlc/regulated-audit/v1"
CRITICAL_ACTIONS = frozenset(
    {
        "approval.add",
        "artifact.add",
        "criterion.satisfy",
        "evidence.add",
        "gate.waive",
        "work.create",
        "work.transition",
    }
)
MANDATORY_HUMAN_ROLES = frozenset({"product-owner", "quality-reviewer"})
NON_COMBINABLE_ROLES = (
    ("architect", "quality-reviewer"),
    ("builder", "quality-reviewer"),
    ("operator", "quality-reviewer"),
    ("product-owner", "quality-reviewer"),
)
EXCEPTION_POLICIES = frozenset({"data-handling", "retention-period", "operational-control"})
AUTHORIZED_EXCEPTION_ROLES = frozenset({"governance-owner"})
CLASSIFICATIONS = frozenset({"public", "internal", "confidential", "restricted"})
DISPOSITIONS = frozenset({"archive", "delete", "review"})
MAX_EXCEPTION_DURATION = timedelta(days=30)
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SENSITIVE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:sk|ghp)_[A-Za-z0-9_-]{8,}|bearer\s+\S+",
    re.IGNORECASE,
)


class RegulatedError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class RegulatedWorkspace(Protocol):
    def project_root(self) -> Path: ...

    def list_actors(self, scope: str = "all") -> list[ActorRecord]: ...

    def show_swarm(self, swarm_id: str) -> SwarmRecord: ...

    def assign_actor(self, data: AssignActorInput) -> SwarmRecord: ...

    def prepare_work_transition(self, data: PrepareWorkTransitionInput) -> LifecycleActionRecord: ...

    def prepare_add_evidence(self, data: PrepareEvidenceInput) -> LifecycleActionRecord: ...

    def apply_lifecycle_action(self, data: ApplyLifecycleActionInput) -> LifecycleActionRecord: ...


@dataclass(frozen=True)
class ExceptionRecord:
    id: str
    policy: str
    reason: str
    authorized_by: str
    authorized_role: str
    created_at: str
    expires_at: str
    evidence: str


@dataclass(frozen=True)
class EvidenceRetention:
    id: str
    evidence_ref: str
    owner: str
    classification: str
    policy: str
    recorded_at: str
    retain_until: str
    disposition: str


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\x00" in value:
        raise RegulatedError("regulated.record.field", f"{label} must be a non-empty single-line string")
    cleaned = value.strip()
    if SENSITIVE.search(cleaned):
        raise RegulatedError("regulated.record.secret", f"{label} must not contain credentials or private keys")
    return cleaned


def _slug(value: str, label: str) -> str:
    cleaned = _text(value, label)
    if SLUG.fullmatch(cleaned) is None:
        raise RegulatedError("regulated.record.id", f"{label} must be a lowercase slug")
    return cleaned


def _instant(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (AttributeError, ValueError) as error:
        raise RegulatedError("regulated.record.time", f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise RegulatedError("regulated.record.time", f"{label} must include a UTC offset")
    return parsed.astimezone(UTC)


def _current(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RegulatedError("regulated.record.time", "evaluation time must include a UTC offset")
    return value.astimezone(UTC)


def _actor_index(workspace: RegulatedWorkspace) -> dict[str, ActorRecord]:
    actors = workspace.list_actors()
    index = {actor.reference: actor for actor in actors}
    ids: dict[str, list[ActorRecord]] = {}
    for actor in actors:
        ids.setdefault(actor.id, []).append(actor)
    for actor_id, matches in ids.items():
        if len(matches) == 1:
            index[actor_id] = matches[0]
    return index


def _blocker(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def assess_assignments(
    workspace: RegulatedWorkspace,
    swarm_id: str,
    proposed: AssignActorInput | None = None,
) -> dict:
    """Assess current or proposed assignments before a regulated actor is used."""
    swarm = workspace.show_swarm(swarm_id)
    actors = _actor_index(workspace)
    assignments = dict(swarm.assignments)
    blockers: list[dict[str, str]] = []
    if proposed is not None:
        if proposed.swarm_id != swarm_id:
            raise RegulatedError("regulated.assignment.swarm", "proposed assignment targets another swarm")
        target = actors.get(proposed.actor_id)
        if target is None:
            blockers.append(_blocker("regulated.assignment.actor", "proposed actor is unavailable"))
        else:
            assignments[proposed.role_id] = target.reference
    else:
        missing = sorted(set(swarm.required_roles) - set(assignments))
        if missing:
            blockers.append(
                _blocker(
                    "regulated.assignment.incomplete",
                    f"required roles are unassigned: {', '.join(missing)}",
                )
            )

    resolved: dict[str, ActorRecord] = {}
    for role, reference in assignments.items():
        actor = actors.get(reference)
        if actor is None:
            blockers.append(_blocker("regulated.assignment.actor", f"actor for role {role} is unavailable"))
            continue
        resolved[role] = actor
        if role in MANDATORY_HUMAN_ROLES and actor.kind != "human":
            blockers.append(_blocker("regulated.assignment.human", f"role {role} requires a human actor"))
        if role in swarm.required_roles and (
            not actor.authentication_required
            or actor.authentication_algorithm != "ed25519"
            or not actor.authentication_fingerprint
            or actor.authentication_revoked_at is not None
        ):
            blockers.append(
                _blocker(
                    "regulated.assignment.signature",
                    f"actor assigned to {role} needs an active Core Ed25519 identity",
                )
            )

    for left, right in NON_COMBINABLE_ROLES:
        if left in resolved and right in resolved and resolved[left].reference == resolved[right].reference:
            blockers.append(
                _blocker(
                    "regulated.assignment.segregation",
                    f"roles {left} and {right} cannot be assigned to the same actor",
                )
            )
    return {"allowed": not blockers, "assignments": assignments, "blockers": blockers}


def assign_actor(workspace: RegulatedWorkspace, data: AssignActorInput) -> SwarmRecord:
    decision = assess_assignments(workspace, data.swarm_id, data)
    if not decision["allowed"]:
        first = decision["blockers"][0]
        raise RegulatedError(first["code"], first["message"])
    return workspace.assign_actor(data)


def require_ready_swarm(workspace: RegulatedWorkspace, swarm_id: str) -> None:
    decision = assess_assignments(workspace, swarm_id)
    if not decision["allowed"]:
        first = decision["blockers"][0]
        raise RegulatedError(first["code"], first["message"])


def _require_signed_actor(workspace: RegulatedWorkspace, actor_id: str, action: str) -> ActorRecord:
    if action not in CRITICAL_ACTIONS:
        raise RegulatedError("regulated.action.kind", f"{action} is not a configured critical action")
    actor = _actor_index(workspace).get(actor_id)
    if actor is None:
        raise RegulatedError("regulated.action.actor", "critical action actor is unavailable")
    if (
        not actor.authentication_required
        or actor.authentication_algorithm != "ed25519"
        or not actor.authentication_fingerprint
        or actor.authentication_revoked_at is not None
    ):
        raise RegulatedError(
            "regulated.action.signature", "critical action actor needs an active Core Ed25519 identity"
        )
    return actor


def prepare_transition(workspace: RegulatedWorkspace, data: PrepareWorkTransitionInput) -> LifecycleActionRecord:
    require_ready_swarm(workspace, data.swarm_id)
    _require_signed_actor(workspace, data.actor_id, "work.transition")
    return workspace.prepare_work_transition(data)


def apply_signed_action(workspace: RegulatedWorkspace, action_id: str, signature: str) -> LifecycleActionRecord:
    if not isinstance(signature, str) or not signature.strip():
        raise RegulatedError("regulated.action.signature", "signature path is required")
    applied = workspace.apply_lifecycle_action(ApplyLifecycleActionInput(action_id=action_id, signature=signature))
    if not applied.authentication_verified:
        raise RuntimeError("Core applied a regulated action without verified authentication")
    return applied


def evaluate_ai_execution(provenance: Provenance) -> dict:
    blockers: list[dict[str, str]] = []
    for name in FIELDS:
        value = getattr(provenance, name)
        if value.value is None or RANK.get(value.source, -1) < RANK["observed"]:
            blockers.append(
                _blocker(
                    "regulated.provenance.incomplete",
                    f"{name} requires an observed value before AI execution",
                )
            )
    if provenance.fallback_source != "observed" or provenance.fallback_used is None:
        blockers.append(
            _blocker(
                "regulated.provenance.incomplete",
                "fallback selection requires an observed value before AI execution",
            )
        )
    return {"allowed": not blockers, "blockers": blockers}


def validate_exception(
    record: ExceptionRecord,
    *,
    authorizers: dict[str, str],
    now: datetime,
) -> dict:
    record_id = _slug(record.id, "exception id")
    if record.policy not in EXCEPTION_POLICIES:
        raise RegulatedError("regulated.exception.policy", "policy is not exception-eligible")
    reason = _text(record.reason, "reason")
    authorized_by = _text(record.authorized_by, "authorized_by")
    authorized_role = _text(record.authorized_role, "authorized_role")
    evidence = _text(record.evidence, "evidence")
    if authorized_role not in AUTHORIZED_EXCEPTION_ROLES or authorizers.get(authorized_by) != authorized_role:
        raise RegulatedError("regulated.exception.authority", "exception authorization is not configured")
    created = _instant(record.created_at, "created_at")
    expires = _instant(record.expires_at, "expires_at")
    current = _current(now)
    if created > current:
        raise RegulatedError("regulated.exception.time", "exception creation time is in the future")
    if expires <= created or expires - created > MAX_EXCEPTION_DURATION:
        raise RegulatedError("regulated.exception.time", "exception must expire within 30 days of creation")
    if current >= expires:
        raise RegulatedError("regulated.exception.expired", "exception has expired")
    return {
        "schema": SCHEMA,
        "kind": "exception",
        "id": record_id,
        "policy": record.policy,
        "reason": reason,
        "authorized_by": authorized_by,
        "authorized_role": authorized_role,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "evidence": evidence,
    }


def validate_retention(record: EvidenceRetention, *, now: datetime) -> dict:
    record_id = _slug(record.id, "retention id")
    evidence_ref = _text(record.evidence_ref, "evidence_ref")
    owner = _text(record.owner, "owner")
    policy = _text(record.policy, "policy")
    if record.classification not in CLASSIFICATIONS:
        raise RegulatedError("regulated.retention.classification", "classification is invalid")
    if record.disposition not in DISPOSITIONS:
        raise RegulatedError("regulated.retention.disposition", "disposition is invalid")
    recorded = _instant(record.recorded_at, "recorded_at")
    retain_until = _instant(record.retain_until, "retain_until")
    current = _current(now)
    if recorded > current or retain_until <= current or retain_until <= recorded:
        raise RegulatedError("regulated.retention.time", "retention interval is not currently valid")
    return {
        "schema": SCHEMA,
        "kind": "evidence-retention",
        "id": record_id,
        "evidence_ref": evidence_ref,
        "owner": owner,
        "classification": record.classification,
        "policy": policy,
        "recorded_at": recorded.isoformat().replace("+00:00", "Z"),
        "retain_until": retain_until.isoformat().replace("+00:00", "Z"),
        "disposition": record.disposition,
    }


def _write_audit(root: Path, category: str, record: dict) -> Path:
    project = root.resolve()
    directory = project
    for component in (".agora", "regulated", category):
        candidate = directory / component
        if candidate.exists() or candidate.is_symlink():
            try:
                resolved = candidate.resolve()
                resolved.relative_to(project)
            except (OSError, ValueError) as error:
                raise RegulatedError("regulated.audit.path", "audit directory escapes the project") from error
            if not resolved.is_dir():
                raise RegulatedError("regulated.audit.path", "audit path component is not a directory")
            directory = resolved
        else:
            candidate.mkdir()
            directory = candidate
    path = directory / f"{record['id']}.json"
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=True, indent=2, sort_keys=True)
            stream.write("\n")
    except FileExistsError as error:
        raise RegulatedError("regulated.audit.immutable", f"audit record already exists: {record['id']}") from error
    return path


def record_exception(
    root: Path,
    record: ExceptionRecord,
    *,
    authorizers: dict[str, str],
    now: datetime,
) -> Path:
    return _write_audit(root, "exceptions", validate_exception(record, authorizers=authorizers, now=now))


def record_evidence_retention(root: Path, record: EvidenceRetention, *, now: datetime) -> Path:
    return _write_audit(root, "evidence-retention", validate_retention(record, now=now))


def prepare_evidence(
    workspace: RegulatedWorkspace,
    data: PrepareEvidenceInput,
    retention: EvidenceRetention,
    *,
    now: datetime,
) -> LifecycleActionRecord:
    require_ready_swarm(workspace, data.swarm_id)
    _require_signed_actor(workspace, data.actor_id, "evidence.add")
    if retention.evidence_ref != (data.evidence_id or data.id):
        raise RegulatedError("regulated.retention.evidence", "retention metadata must identify the prepared evidence")
    validated = validate_retention(retention, now=now)
    _write_audit(workspace.project_root(), "evidence-retention", validated)
    return workspace.prepare_add_evidence(data)
