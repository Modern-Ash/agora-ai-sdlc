"""First-class AI-SDLC Level 1 / Level-N plan artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from agora_ai_sdlc.artifacts import Artifact, ArtifactError, parse_artifact

APPROVAL_STATES = {"pending", "approved", "rejected"}
DECISIONS = {"execute", "skip"}


class PlanError(ValueError):
    """Stable validation error for plan-specific semantics."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class PlanStep:
    id: str
    decision: str
    rationale: str
    dependencies: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    produced_artifacts: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    artifact: Artifact
    level: int
    parent_plan: str | None
    intent: str
    unit: str | None
    proposed_by: str
    approval_state: str
    approved_by: str | None
    approved_revision: int | None
    steps: tuple[PlanStep, ...]

    @property
    def id(self) -> str:
        return self.artifact.id

    @property
    def revision(self) -> int:
        return int(self.artifact.front["revision"])


def _non_empty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError("plan.type", f"{field!r} must be a non-empty string")
    return value


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _non_empty(value, field)


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise PlanError("plan.type", f"{field!r} must be a list of non-empty strings")
    if len(set(value)) != len(value):
        raise PlanError("plan.duplicate", f"{field!r} contains duplicate values")
    return tuple(value)


def _step(raw: object, index: int, previous: set[str]) -> PlanStep:
    if not isinstance(raw, dict):
        raise PlanError("plan.step_type", f"steps[{index}] must be a mapping")
    expected = {
        "id",
        "decision",
        "rationale",
        "dependencies",
        "required-artifacts",
        "produced-artifacts",
    }
    if set(raw) != expected:
        raise PlanError("plan.step_fields", f"steps[{index}] must contain exactly {sorted(expected)}")

    step_id = _non_empty(raw["id"], f"steps[{index}].id")
    decision = _non_empty(raw["decision"], f"steps[{index}].decision")
    if decision not in DECISIONS:
        raise PlanError("plan.step_decision", f"steps[{index}] decision must be execute or skip")
    rationale = _non_empty(raw["rationale"], f"steps[{index}].rationale")
    dependencies = _string_list(raw["dependencies"], f"steps[{index}].dependencies")
    unknown = [dependency for dependency in dependencies if dependency not in previous]
    if unknown:
        raise PlanError(
            "plan.step_dependency",
            f"steps[{index}] dependencies must reference earlier steps: {', '.join(unknown)}",
        )
    required = _string_list(raw["required-artifacts"], f"steps[{index}].required-artifacts")
    produced = _string_list(raw["produced-artifacts"], f"steps[{index}].produced-artifacts")
    return PlanStep(step_id, decision, rationale, dependencies, required, produced)


def parse_plan(text: str) -> Plan:
    """Parse a filled generic artifact and enforce plan-specific semantics."""

    try:
        artifact = parse_artifact(text)
    except ArtifactError as error:
        raise PlanError("plan.artifact", str(error)) from error
    if artifact.kind != "plan":
        raise PlanError("plan.kind", f"expected plan artifact, got {artifact.kind!r}")

    front = artifact.front
    level = front.get("level")
    if isinstance(level, bool) or not isinstance(level, int) or level < 1:
        raise PlanError("plan.level", "level must be a positive integer")

    parent = _optional_string(front.get("parent-plan"), "parent-plan")
    if level == 1 and parent is not None:
        raise PlanError("plan.parent_level1", "Level 1 plan must not declare parent-plan")
    if level > 1 and parent is None:
        raise PlanError("plan.parent_required", "Level N plan must declare parent-plan")

    intent = _non_empty(front.get("intent"), "intent")
    if not intent.startswith("INT-"):
        raise PlanError("plan.intent", "intent must reference an INT-NNN artifact")
    unit = _optional_string(front.get("unit"), "unit")
    if unit is not None and not unit.startswith("UOW-"):
        raise PlanError("plan.unit", "unit must reference a UOW-NNN artifact")

    proposed_by = _non_empty(front.get("proposed-by"), "proposed-by")
    approval_state = _non_empty(front.get("approval-state"), "approval-state")
    if approval_state not in APPROVAL_STATES:
        raise PlanError("plan.approval_state", f"unsupported approval state {approval_state!r}")

    approved_by = _optional_string(front.get("approved-by"), "approved-by")
    approved_revision = front.get("approved-revision")
    if approved_revision is not None and (
        isinstance(approved_revision, bool) or not isinstance(approved_revision, int)
    ):
        raise PlanError("plan.approval_revision", "approved-revision must be an integer or null")

    revision = front.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise PlanError("plan.revision", "revision must be a positive integer")

    if approval_state == "approved":
        if approved_by is None:
            raise PlanError("plan.approver_required", "approved plan requires approved-by")
        if approved_revision != revision:
            raise PlanError(
                "plan.approval_stale",
                f"approved-revision {approved_revision!r} does not match current revision {revision}",
            )
    elif approved_by is not None or approved_revision is not None:
        raise PlanError(
            "plan.approval_inconsistent",
            "pending/rejected plan must not retain approved-by or approved-revision",
        )

    raw_steps = front.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise PlanError("plan.steps", "steps must be a non-empty ordered list")
    steps: list[PlanStep] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_steps):
        parsed = _step(raw, index, seen)
        if parsed.id in seen:
            raise PlanError("plan.step_duplicate", f"duplicate step id {parsed.id!r}")
        seen.add(parsed.id)
        steps.append(parsed)

    if parent is not None and parent not in artifact.traces_to:
        raise PlanError("plan.parent_trace", "parent-plan must also appear in traces-to")

    return Plan(
        artifact=artifact,
        level=level,
        parent_plan=parent,
        intent=intent,
        unit=unit,
        proposed_by=proposed_by,
        approval_state=approval_state,
        approved_by=approved_by,
        approved_revision=approved_revision,
        steps=tuple(steps),
    )


def assert_executable(plan: Plan) -> None:
    """Fail closed until the exact current plan revision is approved."""

    if plan.approval_state != "approved":
        raise PlanError("plan.not_approved", f"plan {plan.id} is not approved")
    if plan.approved_revision != plan.revision:
        raise PlanError("plan.approval_stale", f"plan {plan.id} approval does not match current revision")


def validate_plan_graph(plans: list[Plan]) -> None:
    """Validate recursive parent/child planning relationships."""

    by_id: dict[str, Plan] = {}
    for plan in plans:
        if plan.id in by_id:
            raise PlanError("plan.graph_duplicate", f"duplicate plan id {plan.id}")
        by_id[plan.id] = plan

    for plan in plans:
        if plan.level == 1:
            continue
        assert plan.parent_plan is not None
        parent = by_id.get(plan.parent_plan)
        if parent is None:
            raise PlanError("plan.parent_missing", f"{plan.id} parent {plan.parent_plan} is missing")
        if parent.level != plan.level - 1:
            raise PlanError(
                "plan.parent_level",
                f"{plan.id} Level {plan.level} parent must be Level {plan.level - 1}",
            )
        if plan.intent != parent.intent or plan.unit != parent.unit:
            raise PlanError("plan.scope_mismatch", f"{plan.id} scope differs from parent {parent.id}")

    for plan in plans:
        visited: set[str] = set()
        current = plan
        while current.parent_plan is not None:
            if current.id in visited:
                raise PlanError("plan.cycle", f"cycle detected from {plan.id}")
            visited.add(current.id)
            parent = by_id.get(current.parent_plan)
            if parent is None:
                break
            current = parent
