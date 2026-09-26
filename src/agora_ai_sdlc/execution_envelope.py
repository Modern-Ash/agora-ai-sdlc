"""ExecutionEnvelope v1: the exact next authorized operation, with identities kept separate.

Authority (Core actor + role), runtime transport (agent + model) and the lifecycle operation are
distinct fields. A runtime name is never an actor id, and adapters only transport the envelope.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_requirements import ExecutionRequirements
from agora_ai_sdlc.runtime_domain import RuntimeBinding, normalize_runtime
from agora_ai_sdlc.runtime_selection import admit_binding

ENVELOPE_SCHEMA = "agora-ai-sdlc/execution-envelope/v1"
STOP_OPERATION = "stop.human_authority"


class EnvelopeError(ValueError):
    """Typed, stable envelope failure raised before any executor launch."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class CoreSnapshot:
    """Authoritative facts consumed by the envelope; read from Core, never from the agent."""

    swarm: str
    work: str
    revision: str
    state: str | None
    target: str | None
    role: str | None
    assignments: Mapping[str, str]
    actors: frozenset[str]
    human_boundary: bool


def snapshot_from_workspace(workspace: Any, status: Any) -> CoreSnapshot:
    """Build a snapshot from Core (`AgoraWorkspace`) and the AI-SDLC iteration status."""
    swarm = workspace.show_swarm(status.swarm)
    return CoreSnapshot(
        swarm=status.swarm,
        work=status.work,
        revision=workspace.work_inspection_read_set_sha256(status.swarm, status.work),
        state=status.state,
        target=status.target,
        role=status.role,
        assignments=dict(swarm.assignments),
        actors=frozenset(actor.reference for actor in workspace.list_actors()),
        human_boundary=bool(status.missing_approvals),
    )


def transition_for(snapshot: CoreSnapshot, bundle: ExecutionBundle) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Deterministic operation id and ordered typed arguments for the next bounded action."""
    if snapshot.human_boundary or bundle.next_action == "human-approval":
        return STOP_OPERATION, (("work", snapshot.work),)
    if bundle.next_action == "governed-transition" and snapshot.target:
        return "lifecycle.transition", (("work", snapshot.work), ("target", snapshot.target))
    return f"{snapshot.state or 'unknown'}.execute", (("work", snapshot.work),)


def _display(operation: str, arguments: tuple[tuple[str, str], ...]) -> str:
    return " ".join([operation, *(f"--{name} {value}" for name, value in arguments)])


@dataclass(frozen=True)
class ExecutionEnvelope:
    swarm: str
    work: str
    revision: str
    actor_id: str
    role: str
    human_boundary: bool
    requirements: dict
    binding: RuntimeBinding | None
    operation: str
    arguments: tuple[tuple[str, str], ...]
    candidate: Mapping[str, Any] | None = None
    context: Mapping[str, Any] | None = None

    @property
    def executable(self) -> bool:
        return not self.human_boundary and self.operation != STOP_OPERATION and self.binding is not None

    def _body(self) -> dict:
        runtime = None
        if self.binding is not None:
            runtime = self.binding.to_dict()
            runtime.pop("schema")
        body = {
            "schema": ENVELOPE_SCHEMA,
            "work": {"swarm": self.swarm, "id": self.work, "revision": self.revision},
            "authority": {"actor_id": self.actor_id, "role": self.role, "human_boundary": self.human_boundary},
            "requirements": self.requirements,
            "runtime": runtime,
            "executable": self.executable,
            "next_transition": {
                "operation": self.operation,
                "arguments": [{"name": name, "value": value} for name, value in self.arguments],
            },
            "display": _display(self.operation, self.arguments),
        }
        if self.candidate is not None:
            body["candidate"] = dict(self.candidate)
        if self.context is not None:
            body["context"] = dict(self.context)
        return body

    def to_dict(self) -> dict:
        body = self._body()
        return {**body, "digest": _digest(body)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _digest(body: Mapping) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def build_envelope(
    snapshot: CoreSnapshot,
    requirements: ExecutionRequirements,
    binding: RuntimeBinding | None,
    bundle: ExecutionBundle,
    *,
    actor_id: str,
    availability: Mapping[str, Any] | None = None,
    candidate: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> ExecutionEnvelope:
    """Build before launch. The responsible actor is explicit and never derived from the runtime."""
    role = snapshot.role
    if not role:
        raise EnvelopeError("envelope.role_missing", "Core reports no responsible role for this work")
    if actor_id not in snapshot.actors:
        raise EnvelopeError("envelope.actor_missing", f"actor {actor_id!r} does not exist in Core")
    if snapshot.assignments.get(role) != actor_id:
        raise EnvelopeError("envelope.actor_unauthorized", f"actor {actor_id!r} does not hold role {role!r}")
    operation, arguments = transition_for(snapshot, bundle)
    stop = snapshot.human_boundary or requirements.human_authority_required or operation == STOP_OPERATION
    if stop:
        return ExecutionEnvelope(
            snapshot.swarm, snapshot.work, snapshot.revision, actor_id, role, True,
            requirements.to_dict(), None, STOP_OPERATION, (("work", snapshot.work),), candidate, context,
        )  # fmt: skip
    if binding is None:
        raise EnvelopeError("envelope.binding_missing", "an executable envelope requires a runtime binding")
    blockers = admit_binding(binding, requirements, availability)
    if blockers:
        codes = ",".join(blocker["code"] for blocker in blockers)
        raise EnvelopeError("envelope.binding_inadmissible", f"runtime binding is not admissible: {codes}")
    return ExecutionEnvelope(
        snapshot.swarm, snapshot.work, snapshot.revision, actor_id, role, False,
        requirements.to_dict(), binding, operation, arguments, candidate, context,
    )  # fmt: skip


@dataclass(frozen=True)
class EnvelopeCheck:
    valid: bool
    reasons: tuple[str, ...]

    @property
    def must_recalculate(self) -> bool:
        return not self.valid

    def to_dict(self) -> dict:
        return {"valid": self.valid, "reasons": list(self.reasons), "must_recalculate": self.must_recalculate}


def verify_integrity(payload: Mapping[str, Any]) -> ExecutionEnvelope:
    """Adapter-facing boundary: reject any envelope whose content no longer matches its digest."""
    try:
        digest = payload["digest"]
        body = {key: value for key, value in payload.items() if key != "digest"}
        if _digest(body) != digest:
            raise EnvelopeError("envelope.tampered", "envelope content does not match its digest")
        if body["schema"] != ENVELOPE_SCHEMA:
            raise EnvelopeError("envelope.schema", "unsupported envelope schema")
        arguments = tuple((item["name"], item["value"]) for item in body["next_transition"]["arguments"])
        operation = body["next_transition"]["operation"]
        if body["display"] != _display(operation, arguments):
            raise EnvelopeError("envelope.tampered", "display rendering diverges from structured transition")
        runtime = body["runtime"]
        binding = None
        if runtime is not None:
            binding = normalize_runtime(runtime)
        envelope = ExecutionEnvelope(
            body["work"]["swarm"], body["work"]["id"], body["work"]["revision"],
            body["authority"]["actor_id"], body["authority"]["role"], body["authority"]["human_boundary"],
            body["requirements"], binding, operation, arguments, body.get("candidate"), body.get("context"),
        )  # fmt: skip
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, EnvelopeError):
            raise
        raise EnvelopeError("envelope.malformed", "envelope is malformed") from error
    if envelope.to_dict() != dict(payload):
        raise EnvelopeError("envelope.tampered", "envelope is not canonical")
    return envelope


def validate_current(
    envelope: ExecutionEnvelope,
    snapshot: CoreSnapshot,
    requirements: ExecutionRequirements,
    *,
    availability: Mapping[str, Any] | None = None,
) -> EnvelopeCheck:
    """Revalidate against current Core state before mutation-bearing execution."""
    reasons: list[str] = []
    if (snapshot.swarm, snapshot.work) != (envelope.swarm, envelope.work):
        reasons.append("envelope.work_mismatch")
    if snapshot.revision != envelope.revision:
        reasons.append("envelope.stale_revision")
    if snapshot.human_boundary and not envelope.human_boundary:
        reasons.append("envelope.human_boundary_appeared")
    if envelope.actor_id not in snapshot.actors or snapshot.assignments.get(envelope.role) != envelope.actor_id:
        reasons.append("envelope.actor_unauthorized")
    if envelope.binding is not None and admit_binding(envelope.binding, requirements, availability):
        reasons.append("envelope.binding_inadmissible")
    return EnvelopeCheck(not reasons, tuple(reasons))
