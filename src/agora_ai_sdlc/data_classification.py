"""Deterministic data-classification and runtime-eligibility policy checks."""

import hashlib
import json
from dataclasses import dataclass

from agora_ai_sdlc.provenance import RANK, Provenance, Value, normalize

SCHEMA = "agora-ai-sdlc/launch-authorization/v1"
CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")
EXECUTION_BOUNDARIES = ("local", "customer-controlled", "external")
UNKNOWN_DEFAULTS = ("deny", *CLASSIFICATIONS)


@dataclass(frozen=True)
class ClassifiedInput:
    id: str
    classification: str | None
    revision: int


@dataclass(frozen=True)
class RuntimeEligibility:
    runtime: str
    max_classification: str
    execution_boundaries: tuple[str, ...]
    revision: int
    evidence: str


@dataclass(frozen=True)
class DataPolicy:
    unknown_default: str = "deny"
    min_runtime_source: str = "declared"
    min_boundary_source: str = "declared"


@dataclass(frozen=True)
class LaunchAuthorization:
    schema: str
    fingerprint: str
    runtime: str
    execution_boundary: str
    effective_classification: str
    eligibility_revision: int
    inputs: tuple[tuple[str, int, str], ...]


def _blocker(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _validate_policy(policy: DataPolicy) -> None:
    if policy.unknown_default not in UNKNOWN_DEFAULTS:
        raise ValueError(f"unknown_default must be one of {', '.join(UNKNOWN_DEFAULTS)}")
    for field in ("min_runtime_source", "min_boundary_source"):
        if getattr(policy, field) not in ("declared", "observed"):
            raise ValueError(f"{field} must be declared or observed")


def _input_snapshot(
    inputs: list[ClassifiedInput], unknown_default: str
) -> tuple[tuple[tuple[str, int, str], ...], tuple[str, ...]]:
    seen: set[str] = set()
    snapshot: list[tuple[str, int, str]] = []
    unknown: list[str] = []
    for item in inputs:
        if not isinstance(item.id, str) or not item.id.strip():
            raise ValueError("input id must be a non-empty string")
        input_id = item.id.strip()
        if input_id in seen:
            raise ValueError(f"duplicate input id: {input_id}")
        seen.add(input_id)
        if not isinstance(item.revision, int) or item.revision < 1:
            raise ValueError(f"input {input_id} revision must be a positive integer")
        classification = item.classification
        if classification not in CLASSIFICATIONS:
            unknown.append(input_id)
            classification = "restricted" if unknown_default == "deny" else unknown_default
        snapshot.append((input_id, item.revision, classification))
    return tuple(sorted(snapshot)), tuple(sorted(unknown))


def _eligibility_blockers(eligibility: RuntimeEligibility) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if not isinstance(eligibility.runtime, str) or not eligibility.runtime.strip():
        blockers.append(_blocker("runtime.eligibility.runtime", "eligibility runtime is required"))
    if eligibility.max_classification not in CLASSIFICATIONS:
        blockers.append(_blocker("runtime.eligibility.classification", "eligibility maximum classification is invalid"))
    if not eligibility.execution_boundaries or any(
        boundary not in EXECUTION_BOUNDARIES for boundary in eligibility.execution_boundaries
    ):
        blockers.append(_blocker("runtime.eligibility.boundary", "eligibility execution boundaries are invalid"))
    if not isinstance(eligibility.revision, int) or eligibility.revision < 1:
        blockers.append(_blocker("runtime.eligibility.revision", "eligibility revision must be positive"))
    if not isinstance(eligibility.evidence, str) or not eligibility.evidence.strip():
        blockers.append(_blocker("runtime.eligibility.evidence", "eligibility evidence is required"))
    return blockers


def _value_is_proven(value: Value, minimum: str) -> bool:
    return value.value is not None and RANK.get(value.source, -1) >= RANK[minimum]


def _authorization(
    *,
    snapshot: tuple[tuple[str, int, str], ...],
    runtime: str,
    boundary: str,
    effective: str,
    eligibility_revision: int,
) -> LaunchAuthorization:
    payload = {
        "schema": SCHEMA,
        "runtime": runtime,
        "execution_boundary": boundary,
        "effective_classification": effective,
        "eligibility_revision": eligibility_revision,
        "inputs": snapshot,
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return LaunchAuthorization(fingerprint=fingerprint, **payload)


def evaluate_launch(
    *,
    inputs: list[ClassifiedInput],
    runtime: Provenance,
    execution_boundary: Value,
    eligibility: RuntimeEligibility,
    policy: DataPolicy | None = None,
) -> dict:
    """Evaluate launch eligibility without reading or returning input contents."""
    policy = policy or DataPolicy()
    _validate_policy(policy)
    snapshot, unknown = _input_snapshot(inputs, policy.unknown_default)
    blockers = _eligibility_blockers(eligibility)

    if unknown and policy.unknown_default == "deny":
        blockers.append(
            _blocker(
                "classification.unknown",
                f"classification is unavailable for input references: {', '.join(unknown)}",
            )
        )

    if not _value_is_proven(runtime.runtime, policy.min_runtime_source):
        blockers.append(_blocker("runtime.identity.unproven", "runtime identity cannot be proven"))
    elif normalize(runtime.runtime.value) != normalize(eligibility.runtime):
        blockers.append(_blocker("runtime.identity.ineligible", "runtime identity has no matching eligibility"))

    if not _value_is_proven(execution_boundary, policy.min_boundary_source):
        blockers.append(_blocker("runtime.boundary.unproven", "execution boundary cannot be proven"))
        boundary = None
    else:
        boundary = normalize(execution_boundary.value)
        if not isinstance(eligibility.execution_boundaries, tuple) or boundary not in eligibility.execution_boundaries:
            blockers.append(_blocker("runtime.boundary.ineligible", "execution boundary is not eligible"))

    effective = max((row[2] for row in snapshot), key=CLASSIFICATIONS.index, default="public")
    offending = tuple(
        row[0]
        for row in snapshot
        if eligibility.max_classification in CLASSIFICATIONS
        and CLASSIFICATIONS.index(row[2]) > CLASSIFICATIONS.index(eligibility.max_classification)
    )
    if offending:
        blockers.append(
            _blocker(
                "classification.exceeds_runtime",
                f"runtime maximum classification is exceeded by input references: {', '.join(offending)}",
            )
        )

    authorization = None
    if not blockers:
        authorization = _authorization(
            snapshot=snapshot,
            runtime=runtime.runtime.value,
            boundary=boundary,
            effective=effective,
            eligibility_revision=eligibility.revision,
        )
    offending_inputs = offending
    if policy.unknown_default == "deny" and not offending_inputs:
        offending_inputs = unknown
    return {
        "allowed": not blockers,
        "effective_classification": effective,
        "offending_inputs": offending_inputs,
        "blockers": blockers,
        "authorization": authorization,
    }


def validate_authorization(
    authorization: LaunchAuthorization,
    *,
    inputs: list[ClassifiedInput],
    runtime: Provenance,
    execution_boundary: Value,
    eligibility: RuntimeEligibility,
    policy: DataPolicy | None = None,
) -> dict:
    """Re-evaluate current metadata and reject an authorization for any stale snapshot."""
    current = evaluate_launch(
        inputs=inputs,
        runtime=runtime,
        execution_boundary=execution_boundary,
        eligibility=eligibility,
        policy=policy,
    )
    if not current["allowed"]:
        return current
    if authorization != current["authorization"]:
        return {
            **current,
            "allowed": False,
            "blockers": [_blocker("authorization.stale", "launch authorization does not match current metadata")],
            "authorization": None,
        }
    return current
