"""Governed change/configuration chain semantics."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agora_ai_sdlc.artifacts import ID_PATTERN, Artifact, ArtifactError, parse_artifact

APPROVAL_STATES = {"pending", "approved", "rejected"}
RISK = {"low", "medium", "high", "critical"}
REF = re.compile(r"^[a-z][a-z0-9+.-]*:[^\s]+$")
FORBIDDEN_VALUE_KEYS = {"secret", "password", "token", "api_key", "apikey", "credential", "credentials", "authorization"}


class ChangeManagementError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class ChangeRequest:
    artifact: Artifact
    requested_by: str
    reason: str
    scope: tuple[str, ...]
    risk: str


@dataclass(frozen=True)
class ChangePlan:
    artifact: Artifact
    change_request: str
    execution_plan: str | None
    steps: tuple[str, ...]
    release_targets: tuple[str, ...]
    rollback_plan: str
    approval_state: str
    approved_by: str | None
    approved_revision: int | None

    @property
    def revision(self) -> int:
        return int(self.artifact.front["revision"])


@dataclass(frozen=True)
class ConfigurationChange:
    key: str
    before: str
    after: str
    resource: str


@dataclass(frozen=True)
class ConfigurationDelta:
    artifact: Artifact
    change_plan: str
    changes: tuple[ConfigurationChange, ...]
    release_evidence: tuple[str, ...]
    rollback_linkage: tuple[str, ...]


@dataclass(frozen=True)
class ChangeChain:
    request: ChangeRequest
    plan: ChangePlan
    delta: ConfigurationDelta


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChangeManagementError("change.type", f"{field!r} must be a non-empty string")
    return value.strip()


def _strings(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ChangeManagementError("change.type", f"{field!r} must be a list of non-empty strings")
    normalized = tuple(item.strip() for item in value)
    if not allow_empty and not normalized:
        raise ChangeManagementError("change.type", f"{field!r} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ChangeManagementError("change.duplicate", f"{field!r} contains duplicates")
    return normalized


def _ref(value: str, field: str) -> str:
    if REF.fullmatch(value) is None:
        raise ChangeManagementError("change.reference", f"{field!r} must be a credential-free opaque/local reference")
    lowered = value.casefold()
    if any(marker in lowered for marker in ("token=", "password=", "secret=", "api_key=", "apikey=", "authorization=")):
        raise ChangeManagementError("change.reference_secret", f"{field!r} contains forbidden credential material")
    return value


def parse_change_request(text: str) -> ChangeRequest:
    try:
        artifact = parse_artifact(text)
    except ArtifactError as error:
        raise ChangeManagementError("change.artifact", str(error)) from error
    if artifact.kind != "change-request":
        raise ChangeManagementError("change.kind", f"expected change-request, got {artifact.kind!r}")
    front = artifact.front
    risk = _string(front.get("risk"), "risk")
    if risk not in RISK:
        raise ChangeManagementError("change.risk", f"unsupported risk {risk!r}")
    return ChangeRequest(
        artifact,
        _string(front.get("requested-by"), "requested-by"),
        _string(front.get("reason"), "reason"),
        _strings(front.get("scope"), "scope"),
        risk,
    )


def parse_change_plan(text: str) -> ChangePlan:
    try:
        artifact = parse_artifact(text)
    except ArtifactError as error:
        raise ChangeManagementError("change.artifact", str(error)) from error
    if artifact.kind != "change-plan":
        raise ChangeManagementError("change.kind", f"expected change-plan, got {artifact.kind!r}")
    front = artifact.front
    request = _string(front.get("change-request"), "change-request")
    if not ID_PATTERN.fullmatch(request) or not request.startswith("CRQ-"):
        raise ChangeManagementError("change.request_ref", "change-request must reference CRQ-NNN")
    execution_plan = front.get("execution-plan")
    if execution_plan is not None:
        execution_plan = _string(execution_plan, "execution-plan")
        if not ID_PATTERN.fullmatch(execution_plan) or not execution_plan.startswith("PLN-"):
            raise ChangeManagementError("change.execution_plan", "execution-plan must reference PLN-NNN")
    rollback_plan = _ref(_string(front.get("rollback-plan"), "rollback-plan"), "rollback-plan")
    approval = _string(front.get("approval-state"), "approval-state")
    if approval not in APPROVAL_STATES:
        raise ChangeManagementError("change.approval_state", f"unsupported approval state {approval!r}")
    approved_by = front.get("approved-by")
    if approved_by is not None:
        approved_by = _string(approved_by, "approved-by")
    approved_revision = front.get("approved-revision")
    revision = front.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ChangeManagementError("change.revision", "revision must be a positive integer")
    if approved_revision is not None and (isinstance(approved_revision, bool) or not isinstance(approved_revision, int)):
        raise ChangeManagementError("change.approval_revision", "approved-revision must be integer or null")
    if approval == "approved":
        if approved_by is None:
            raise ChangeManagementError("change.approver_required", "approved change plan requires approved-by")
        if approved_revision != revision:
            raise ChangeManagementError("change.approval_stale", "approved-revision must match current revision")
    elif approved_by is not None or approved_revision is not None:
        raise ChangeManagementError("change.approval_inconsistent", "pending/rejected plan cannot retain approval")
    if request not in artifact.traces_to:
        raise ChangeManagementError("change.request_trace", "change-request must appear in traces-to")
    if execution_plan is not None and execution_plan not in artifact.traces_to:
        raise ChangeManagementError("change.execution_trace", "execution-plan must appear in traces-to")
    return ChangePlan(
        artifact,
        request,
        execution_plan,
        _strings(front.get("steps"), "steps"),
        _strings(front.get("release-targets"), "release-targets"),
        rollback_plan,
        approval,
        approved_by,
        approved_revision,
    )


def _safe_change_value(value: object, field: str) -> str:
    text = _string(value, field)
    lowered = text.casefold()
    if any(marker in lowered for marker in ("password", "secret", "token", "api_key", "apikey", "authorization")):
        raise ChangeManagementError("change.secret_value", f"{field!r} contains forbidden secret-like data")
    return text


def parse_configuration_delta(text: str) -> ConfigurationDelta:
    try:
        artifact = parse_artifact(text)
    except ArtifactError as error:
        raise ChangeManagementError("change.artifact", str(error)) from error
    if artifact.kind != "configuration-delta":
        raise ChangeManagementError("change.kind", f"expected configuration-delta, got {artifact.kind!r}")
    front = artifact.front
    plan = _string(front.get("change-plan"), "change-plan")
    if not ID_PATTERN.fullmatch(plan) or not plan.startswith("CHP-"):
        raise ChangeManagementError("change.plan_ref", "change-plan must reference CHP-NNN")
    if plan not in artifact.traces_to:
        raise ChangeManagementError("change.plan_trace", "change-plan must appear in traces-to")
    raw_changes = front.get("changes")
    if not isinstance(raw_changes, list) or not raw_changes:
        raise ChangeManagementError("change.delta", "changes must be a non-empty list")
    parsed = []
    for index, raw in enumerate(raw_changes):
        if not isinstance(raw, dict) or set(raw) != {"key", "before", "after", "resource"}:
            raise ChangeManagementError("change.delta_fields", f"changes[{index}] has invalid fields")
        key = _string(raw["key"], f"changes[{index}].key")
        if key.casefold() in FORBIDDEN_VALUE_KEYS:
            raise ChangeManagementError("change.secret_key", f"changes[{index}].key is forbidden")
        parsed.append(
            ConfigurationChange(
                key,
                _safe_change_value(raw["before"], f"changes[{index}].before"),
                _safe_change_value(raw["after"], f"changes[{index}].after"),
                _string(raw["resource"], f"changes[{index}].resource"),
            )
        )
    release = tuple(_ref(item, "release-evidence") for item in _strings(front.get("release-evidence"), "release-evidence"))
    rollback = tuple(_ref(item, "rollback-linkage") for item in _strings(front.get("rollback-linkage"), "rollback-linkage"))
    return ConfigurationDelta(artifact, plan, tuple(parsed), release, rollback)


def assert_approved(plan: ChangePlan) -> None:
    if plan.approval_state != "approved" or plan.approved_revision != plan.revision:
        raise ChangeManagementError("change.not_approved", f"change plan {plan.artifact.id} is not approved")


def validate_chain(request: ChangeRequest, plan: ChangePlan, delta: ConfigurationDelta) -> ChangeChain:
    assert_approved(plan)
    if plan.change_request != request.artifact.id:
        raise ChangeManagementError("change.chain_request", "change plan does not reference the supplied change request")
    if delta.change_plan != plan.artifact.id:
        raise ChangeManagementError("change.chain_plan", "configuration delta does not reference the supplied change plan")
    return ChangeChain(request, plan, delta)


def summary(chain: ChangeChain) -> dict:
    return {
        "change_request": chain.request.artifact.id,
        "change_plan": chain.plan.artifact.id,
        "configuration_delta": chain.delta.artifact.id,
        "risk": chain.request.risk,
        "release_evidence": list(chain.delta.release_evidence),
        "rollback_linkage": list(chain.delta.rollback_linkage),
        "change_count": len(chain.delta.changes),
        "approved": True,
    }
