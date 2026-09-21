"""First-class Bolt plans: executable, human-validated iterations over a Unit of Work."""

from __future__ import annotations

from dataclasses import dataclass

from agora_ai_sdlc.artifacts import ID_PATTERN, SLUG, Artifact, ArtifactError, parse_artifact

APPROVAL_STATES = {"pending", "approved", "rejected"}
MODES = {"sequential", "parallel"}
STATUSES = ("proposed", "approved", "running", "completed", "failed")
# Forward lifecycle; `failed` is reachable from `running` only and is terminal for the Bolt.
TRANSITIONS = {
    "proposed": {"approved"},
    "approved": {"running"},
    "running": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}
DONE = "completed"


class BoltError(ValueError):
    """Stable validation error for Bolt-specific semantics."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Bolt:
    id: str
    mode: str
    status: str
    tasks: tuple[str, ...]
    depends_on: tuple[str, ...]
    writes: tuple[str, ...]
    produces: tuple[str, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class BoltPlan:
    artifact: Artifact
    unit: str
    plan: str | None
    proposed_by: str
    approval_state: str
    approved_by: str | None
    approved_revision: int | None
    bolts: tuple[Bolt, ...]

    @property
    def id(self) -> str:
        return self.artifact.id

    @property
    def revision(self) -> int:
        return int(self.artifact.front["revision"])


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BoltError("bolt.type", f"{field!r} must be a non-empty string")
    return value


def _strings(value: object, field: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise BoltError("bolt.type", f"{field!r} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise BoltError("bolt.type", f"{field!r} must not be empty")
    if len(set(value)) != len(value):
        raise BoltError("bolt.duplicate", f"{field!r} contains duplicate values")
    return tuple(value)


def _bolt(raw: object, index: int, previous: set[str]) -> Bolt:
    if not isinstance(raw, dict):
        raise BoltError("bolt.entry_type", f"bolts[{index}] must be a mapping")
    expected = {"id", "mode", "status", "tasks", "depends-on", "writes", "produces", "evidence"}
    if set(raw) != expected:
        raise BoltError("bolt.entry_fields", f"bolts[{index}] must contain exactly {sorted(expected)}")
    bolt_id = _string(raw["id"], f"bolts[{index}].id")
    if not SLUG.fullmatch(bolt_id):
        raise BoltError("bolt.id", f"bolts[{index}].id must be a lowercase slug")
    mode = raw["mode"]
    if mode not in MODES:
        raise BoltError("bolt.mode", f"bolts[{index}] mode must be sequential or parallel")
    status = raw["status"]
    if status not in STATUSES:
        raise BoltError("bolt.status", f"bolts[{index}] status must be one of {', '.join(STATUSES)}")
    depends = _strings(raw["depends-on"], f"bolts[{index}].depends-on")
    unknown = [dep for dep in depends if dep not in previous]
    if unknown:
        raise BoltError(
            "bolt.dependency",
            f"bolts[{index}] dependencies must reference earlier bolts: {', '.join(unknown)}",
        )
    produces = _strings(raw["produces"], f"bolts[{index}].produces")
    for ref in produces:
        if not ID_PATTERN.fullmatch(ref):
            raise BoltError("bolt.produces", f"bolts[{index}] produces malformed artifact id {ref!r}")
    return Bolt(
        bolt_id,
        mode,
        status,
        _strings(raw["tasks"], f"bolts[{index}].tasks", allow_empty=False),
        depends,
        _strings(raw["writes"], f"bolts[{index}].writes"),
        produces,
        _strings(raw["evidence"], f"bolts[{index}].evidence"),
    )


def _ancestors(bolts: tuple[Bolt, ...]) -> dict[str, frozenset[str]]:
    """Transitive dependencies per Bolt; dependencies only reference earlier Bolts, so this is acyclic."""

    closure: dict[str, frozenset[str]] = {}
    for bolt in bolts:
        reach: set[str] = set()
        for dep in bolt.depends_on:
            reach.add(dep)
            reach |= closure[dep]
        closure[bolt.id] = frozenset(reach)
    return closure


def _overlaps(left: str, right: str) -> bool:
    a, b = left.rstrip("/"), right.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def detect_conflicts(bolts: tuple[Bolt, ...]) -> tuple[tuple[str, str, str, str], ...]:
    """Return (bolt, bolt, path, path) for unordered Bolt pairs whose write sets overlap."""

    closure = _ancestors(bolts)
    found = []
    for i, first in enumerate(bolts):
        for second in bolts[i + 1 :]:
            if first.id in closure[second.id]:
                continue  # ordered by dependency: cannot run concurrently
            for left in first.writes:
                for right in second.writes:
                    if _overlaps(left, right):
                        found.append((first.id, second.id, left, right))
    return tuple(found)


def parse_bolt_plan(text: str) -> BoltPlan:
    """Parse a filled bolt-plan artifact and enforce structure, ordering, lifecycle and conflicts."""

    try:
        artifact = parse_artifact(text)
    except ArtifactError as error:
        raise BoltError("bolt.artifact", str(error)) from error
    if artifact.kind != "bolt-plan":
        raise BoltError("bolt.kind", f"expected bolt-plan artifact, got {artifact.kind!r}")
    front = artifact.front

    unit = _string(front.get("unit"), "unit")
    if not ID_PATTERN.fullmatch(unit) or not unit.startswith("UOW-"):
        raise BoltError("bolt.unit", "unit must reference a UOW-NNN artifact")
    plan = front.get("plan")
    if plan is not None:
        plan = _string(plan, "plan")
        if not ID_PATTERN.fullmatch(plan) or not plan.startswith("PLN-"):
            raise BoltError("bolt.plan", "plan must reference a PLN-NNN artifact")
    proposed_by = _string(front.get("proposed-by"), "proposed-by")
    approval_state = _string(front.get("approval-state"), "approval-state")
    if approval_state not in APPROVAL_STATES:
        raise BoltError("bolt.approval_state", f"unsupported approval state {approval_state!r}")
    approved_by = front.get("approved-by")
    if approved_by is not None:
        approved_by = _string(approved_by, "approved-by")
    approved_revision = front.get("approved-revision")
    if approved_revision is not None and (
        isinstance(approved_revision, bool) or not isinstance(approved_revision, int)
    ):
        raise BoltError("bolt.approval_revision", "approved-revision must be an integer or null")
    revision = front.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise BoltError("bolt.revision", "revision must be a positive integer")
    if approval_state == "approved":
        if approved_by is None:
            raise BoltError("bolt.approver_required", "approved bolt plan requires approved-by")
        if approved_revision != revision:
            raise BoltError(
                "bolt.approval_stale",
                f"approved-revision {approved_revision!r} does not match current revision {revision}",
            )
    elif approved_by is not None or approved_revision is not None:
        raise BoltError(
            "bolt.approval_inconsistent",
            "pending/rejected bolt plan must not retain approved-by or approved-revision",
        )

    if unit not in artifact.traces_to:
        raise BoltError("bolt.unit_trace", "unit must appear in traces-to")
    if plan is not None and plan not in artifact.traces_to:
        raise BoltError("bolt.plan_trace", "plan must also appear in traces-to")

    raw = front.get("bolts")
    if not isinstance(raw, list) or not raw:
        raise BoltError("bolt.bolts", "bolts must be a non-empty ordered list")
    bolts: list[Bolt] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        parsed = _bolt(entry, index, seen)
        if parsed.id in seen:
            raise BoltError("bolt.duplicate_id", f"duplicate bolt id {parsed.id!r}")
        seen.add(parsed.id)
        bolts.append(parsed)
    ordered = tuple(bolts)

    closure = _ancestors(ordered)
    for index, bolt in enumerate(ordered):
        if bolt.mode == "sequential" and closure[bolt.id] != {earlier.id for earlier in ordered[:index]}:
            raise BoltError(
                "bolt.sequential_unordered",
                f"sequential bolt {bolt.id!r} must depend on every earlier bolt",
            )
    conflicts = detect_conflicts(ordered)
    if conflicts:
        first, second, left, right = conflicts[0]
        raise BoltError(
            "bolt.parallel_conflict",
            f"parallel bolts {first!r} and {second!r} write overlapping paths {left!r} / {right!r}",
        )

    by_id = {bolt.id: bolt for bolt in ordered}
    for bolt in ordered:
        if approval_state != "approved" and bolt.status != "proposed":
            raise BoltError(
                "bolt.not_approved",
                f"bolt {bolt.id!r} is {bolt.status} but the bolt plan is not approved for its current revision",
            )
        if bolt.status in {"running", "completed"}:
            pending = [dep for dep in bolt.depends_on if by_id[dep].status != DONE]
            if pending:
                raise BoltError(
                    "bolt.dependency_incomplete",
                    f"bolt {bolt.id!r} is {bolt.status} before dependencies completed: {', '.join(pending)}",
                )
        if bolt.status == "completed" and not bolt.evidence:
            raise BoltError("bolt.evidence_required", f"completed bolt {bolt.id!r} requires evidence links")

    return BoltPlan(artifact, unit, plan, proposed_by, approval_state, approved_by, approved_revision, ordered)


def assert_can_start(bolt_plan: BoltPlan, bolt_id: str) -> None:
    """Fail closed unless the exact current revision is approved and the Bolt's dependencies are complete."""

    if bolt_plan.approval_state != "approved" or bolt_plan.approved_revision != bolt_plan.revision:
        raise BoltError("bolt.not_approved", f"bolt plan {bolt_plan.id} is not approved for its current revision")
    by_id = {bolt.id: bolt for bolt in bolt_plan.bolts}
    bolt = by_id.get(bolt_id)
    if bolt is None:
        raise BoltError("bolt.unknown", f"unknown bolt {bolt_id!r}")
    if "running" not in TRANSITIONS.get(bolt.status, set()):
        raise BoltError("bolt.transition", f"bolt {bolt_id!r} cannot start from status {bolt.status!r}")
    pending = [dep for dep in bolt.depends_on if by_id[dep].status != DONE]
    if pending:
        raise BoltError("bolt.dependency_incomplete", f"bolt {bolt_id!r} waits on: {', '.join(pending)}")


def check_transition(current: str, new: str) -> None:
    if new not in STATUSES or current not in STATUSES:
        raise BoltError("bolt.status", f"unknown status transition {current!r} -> {new!r}")
    if new not in TRANSITIONS[current]:
        raise BoltError("bolt.transition", f"illegal bolt transition {current!r} -> {new!r}")


def ready_bolts(bolt_plan: BoltPlan) -> tuple[str, ...]:
    """Bolts that may start now; more than one entry means they can run in parallel."""

    if bolt_plan.approval_state != "approved":
        return ()
    by_id = {bolt.id: bolt for bolt in bolt_plan.bolts}
    return tuple(
        bolt.id
        for bolt in bolt_plan.bolts
        if bolt.status == "approved" and all(by_id[dep].status == DONE for dep in bolt.depends_on)
    )


def trace(bolt_plan: BoltPlan) -> dict:
    """Unit -> Bolt -> artifacts/evidence, plus whether Bolt evidence is complete for Construction."""

    return {
        "unit": bolt_plan.unit,
        "bolt_plan": bolt_plan.id,
        "revision": bolt_plan.revision,
        "bolts": [
            {
                "id": bolt.id,
                "mode": bolt.mode,
                "status": bolt.status,
                "depends_on": list(bolt.depends_on),
                "artifacts": list(bolt.produces),
                "evidence": list(bolt.evidence),
            }
            for bolt in bolt_plan.bolts
        ],
        "ready": list(ready_bolts(bolt_plan)),
        "construction_evidence_complete": all(bolt.status == DONE for bolt in bolt_plan.bolts),
    }
