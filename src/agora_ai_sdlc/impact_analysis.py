"""Provider-neutral cross-repository impact-analysis artifact semantics."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agora_ai_sdlc.artifacts import ID_PATTERN, SLUG, Artifact, ArtifactError, parse_artifact

APPROVAL_STATES = {"pending", "approved", "rejected"}
CONFIDENCE = {"low", "medium", "high"}
CONTRACT_TYPES = {"api", "event", "schema"}
DEPENDENCY_DIRECTIONS = {"inbound", "outbound", "bidirectional", "unknown"}
DEPENDENCY_STATUS = {"known", "unknown"}
REF_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*:[^\s]+$")


class ImpactAnalysisError(ValueError):
    """Stable validation error for impact-analysis semantics."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class RepositoryImpact:
    id: str
    ref: str | None


@dataclass(frozen=True)
class ComponentImpact:
    repository: str
    name: str
    expected_change: str


@dataclass(frozen=True)
class ContractImpact:
    type: str
    name: str
    repository: str
    expected_change: str


@dataclass(frozen=True)
class DependencyImpact:
    source: str
    target: str
    direction: str
    status: str
    reason: str | None


@dataclass(frozen=True)
class ImpactAnalysis:
    artifact: Artifact
    unit: str
    plan: str | None
    bolt_plans: tuple[str, ...]
    repositories: tuple[RepositoryImpact, ...]
    components: tuple[ComponentImpact, ...]
    contracts: tuple[ContractImpact, ...]
    dependencies: tuple[DependencyImpact, ...]
    expected_changes: tuple[str, ...]
    owners: tuple[str, ...]
    reviewers: tuple[str, ...]
    confidence: str
    unknowns: tuple[str, ...]
    approval_state: str
    approved_by: str | None
    approved_revision: int | None

    @property
    def id(self) -> str:
        return self.artifact.id

    @property
    def revision(self) -> int:
        return int(self.artifact.front["revision"])


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ImpactAnalysisError("impact.type", f"{field!r} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _string(value, field)


def _strings(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ImpactAnalysisError("impact.type", f"{field!r} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise ImpactAnalysisError("impact.type", f"{field!r} must not be empty")
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        raise ImpactAnalysisError("impact.duplicate", f"{field!r} contains duplicate values")
    return normalized


def _repository(raw: object, index: int) -> RepositoryImpact:
    if not isinstance(raw, dict) or set(raw) != {"id", "ref"}:
        raise ImpactAnalysisError("impact.repository_fields", f"repositories[{index}] must contain id/ref")
    repository_id = _string(raw["id"], f"repositories[{index}].id")
    if not SLUG.fullmatch(repository_id):
        raise ImpactAnalysisError("impact.repository_id", f"invalid repository id {repository_id!r}")
    ref = _optional_string(raw["ref"], f"repositories[{index}].ref")
    if ref is not None and REF_PATTERN.fullmatch(ref) is None:
        raise ImpactAnalysisError(
            "impact.repository_ref",
            f"repositories[{index}].ref must be an opaque URI-like reference",
        )
    return RepositoryImpact(repository_id, ref)


def _component(raw: object, index: int, repositories: set[str]) -> ComponentImpact:
    expected = {"repository", "name", "expected-change"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ImpactAnalysisError("impact.component_fields", f"components[{index}] has invalid fields")
    repository = _string(raw["repository"], f"components[{index}].repository")
    if repository not in repositories:
        raise ImpactAnalysisError(
            "impact.repository_unknown", f"component references unknown repository {repository!r}"
        )
    return ComponentImpact(
        repository,
        _string(raw["name"], f"components[{index}].name"),
        _string(raw["expected-change"], f"components[{index}].expected-change"),
    )


def _contract(raw: object, index: int, repositories: set[str]) -> ContractImpact:
    expected = {"type", "name", "repository", "expected-change"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ImpactAnalysisError("impact.contract_fields", f"contracts[{index}] has invalid fields")
    contract_type = _string(raw["type"], f"contracts[{index}].type")
    if contract_type not in CONTRACT_TYPES:
        raise ImpactAnalysisError("impact.contract_type", f"unsupported contract type {contract_type!r}")
    repository = _string(raw["repository"], f"contracts[{index}].repository")
    if repository not in repositories:
        raise ImpactAnalysisError("impact.repository_unknown", f"contract references unknown repository {repository!r}")
    return ContractImpact(
        contract_type,
        _string(raw["name"], f"contracts[{index}].name"),
        repository,
        _string(raw["expected-change"], f"contracts[{index}].expected-change"),
    )


def _dependency(raw: object, index: int, repositories: set[str]) -> DependencyImpact:
    expected = {"source", "target", "direction", "status", "reason"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ImpactAnalysisError("impact.dependency_fields", f"dependencies[{index}] has invalid fields")
    source = _string(raw["source"], f"dependencies[{index}].source")
    target = _string(raw["target"], f"dependencies[{index}].target")
    if source not in repositories or target not in repositories:
        raise ImpactAnalysisError("impact.repository_unknown", "dependency references unknown repository")
    if source == target:
        raise ImpactAnalysisError("impact.dependency_self", "cross-repository dependency endpoints must differ")
    direction = _string(raw["direction"], f"dependencies[{index}].direction")
    if direction not in DEPENDENCY_DIRECTIONS:
        raise ImpactAnalysisError("impact.dependency_direction", f"unsupported dependency direction {direction!r}")
    status = _string(raw["status"], f"dependencies[{index}].status")
    if status not in DEPENDENCY_STATUS:
        raise ImpactAnalysisError("impact.dependency_status", f"unsupported dependency status {status!r}")
    reason = _optional_string(raw["reason"], f"dependencies[{index}].reason")
    if status == "unknown" and reason is None:
        raise ImpactAnalysisError("impact.unknown_reason", "unknown dependency requires a reason")
    if status == "known" and direction == "unknown":
        raise ImpactAnalysisError("impact.dependency_direction", "known dependency cannot use unknown direction")
    return DependencyImpact(source, target, direction, status, reason)


def parse_impact_analysis(text: str) -> ImpactAnalysis:
    """Parse and validate one filled impact-analysis artifact."""

    try:
        artifact = parse_artifact(text)
    except ArtifactError as error:
        raise ImpactAnalysisError("impact.artifact", str(error)) from error
    if artifact.kind != "impact-analysis":
        raise ImpactAnalysisError("impact.kind", f"expected impact-analysis artifact, got {artifact.kind!r}")
    front = artifact.front

    unit = _string(front.get("unit"), "unit")
    if not ID_PATTERN.fullmatch(unit) or not unit.startswith("UOW-"):
        raise ImpactAnalysisError("impact.unit", "unit must reference a UOW-NNN artifact")
    plan = _optional_string(front.get("plan"), "plan")
    if plan is not None and (not ID_PATTERN.fullmatch(plan) or not plan.startswith("PLN-")):
        raise ImpactAnalysisError("impact.plan", "plan must reference a PLN-NNN artifact")
    bolt_plans = _strings(front.get("bolt-plans", []), "bolt-plans", allow_empty=True)
    for bolt_plan in bolt_plans:
        if not ID_PATTERN.fullmatch(bolt_plan) or not bolt_plan.startswith("BLP-"):
            raise ImpactAnalysisError("impact.bolt_plan", f"invalid Bolt Plan reference {bolt_plan!r}")

    raw_repositories = front.get("repositories")
    if not isinstance(raw_repositories, list) or len(raw_repositories) < 2:
        raise ImpactAnalysisError("impact.repositories", "cross-repository analysis requires at least two repositories")
    repositories = tuple(_repository(raw, index) for index, raw in enumerate(raw_repositories))
    repository_ids = [repository.id for repository in repositories]
    if len(repository_ids) != len(set(repository_ids)):
        raise ImpactAnalysisError("impact.repository_duplicate", "repository ids must be unique")
    repository_set = set(repository_ids)

    raw_components = front.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        raise ImpactAnalysisError("impact.components", "components must be a non-empty list")
    components = tuple(_component(raw, index, repository_set) for index, raw in enumerate(raw_components))

    raw_contracts = front.get("contracts")
    if not isinstance(raw_contracts, list) or not raw_contracts:
        raise ImpactAnalysisError("impact.contracts", "contracts must be a non-empty list")
    contracts = tuple(_contract(raw, index, repository_set) for index, raw in enumerate(raw_contracts))

    raw_dependencies = front.get("dependencies")
    if not isinstance(raw_dependencies, list) or not raw_dependencies:
        raise ImpactAnalysisError("impact.dependencies", "dependencies must be a non-empty list")
    dependencies = tuple(_dependency(raw, index, repository_set) for index, raw in enumerate(raw_dependencies))

    expected_changes = _strings(front.get("expected-changes"), "expected-changes")
    owners = _strings(front.get("owners"), "owners")
    reviewers = _strings(front.get("reviewers"), "reviewers")
    if set(owners) >= set(reviewers):
        raise ImpactAnalysisError(
            "impact.reviewer_separation", "at least one reviewer must be distinct from all owners"
        )

    confidence = _string(front.get("confidence"), "confidence")
    if confidence not in CONFIDENCE:
        raise ImpactAnalysisError("impact.confidence", f"confidence must be one of {', '.join(sorted(CONFIDENCE))}")
    unknowns = _strings(front.get("unknowns", []), "unknowns", allow_empty=True)
    unknown_dependencies = [dependency for dependency in dependencies if dependency.status == "unknown"]
    if unknown_dependencies and not unknowns:
        raise ImpactAnalysisError("impact.unknowns", "unknown dependencies require explicit unknowns")

    approval_state = _string(front.get("approval-state"), "approval-state")
    if approval_state not in APPROVAL_STATES:
        raise ImpactAnalysisError("impact.approval_state", f"unsupported approval state {approval_state!r}")
    approved_by = _optional_string(front.get("approved-by"), "approved-by")
    approved_revision = front.get("approved-revision")
    if approved_revision is not None and (
        isinstance(approved_revision, bool) or not isinstance(approved_revision, int)
    ):
        raise ImpactAnalysisError("impact.approval_revision", "approved-revision must be an integer or null")
    revision = front.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ImpactAnalysisError("impact.revision", "revision must be a positive integer")

    if approval_state == "approved":
        if approved_by is None:
            raise ImpactAnalysisError("impact.approver_required", "approved analysis requires approved-by")
        if approved_by not in reviewers:
            raise ImpactAnalysisError("impact.approver_reviewer", "approved-by must be one of the declared reviewers")
        if approved_revision != revision:
            raise ImpactAnalysisError(
                "impact.approval_stale",
                f"approved-revision {approved_revision!r} does not match current revision {revision}",
            )
    elif approved_by is not None or approved_revision is not None:
        raise ImpactAnalysisError(
            "impact.approval_inconsistent",
            "pending/rejected analysis must not retain approved-by or approved-revision",
        )

    if unit not in artifact.traces_to:
        raise ImpactAnalysisError("impact.unit_trace", "unit must appear in traces-to")
    if plan is not None and plan not in artifact.traces_to:
        raise ImpactAnalysisError("impact.plan_trace", "plan must appear in traces-to")
    missing_bolt_traces = [bolt_plan for bolt_plan in bolt_plans if bolt_plan not in artifact.traces_to]
    if missing_bolt_traces:
        raise ImpactAnalysisError(
            "impact.bolt_trace",
            f"Bolt Plan references must appear in traces-to: {', '.join(missing_bolt_traces)}",
        )

    return ImpactAnalysis(
        artifact,
        unit,
        plan,
        bolt_plans,
        repositories,
        components,
        contracts,
        dependencies,
        expected_changes,
        owners,
        reviewers,
        confidence,
        unknowns,
        approval_state,
        approved_by,
        approved_revision,
    )


def assert_approved(analysis: ImpactAnalysis) -> None:
    if analysis.approval_state != "approved" or analysis.approved_revision != analysis.revision:
        raise ImpactAnalysisError(
            "impact.not_approved",
            f"impact analysis {analysis.id} is not approved for its current revision",
        )


def affected_repositories(analysis: ImpactAnalysis) -> tuple[str, ...]:
    return tuple(repository.id for repository in analysis.repositories)


def summary(analysis: ImpactAnalysis) -> dict:
    return {
        "id": analysis.id,
        "unit": analysis.unit,
        "plan": analysis.plan,
        "bolt_plans": list(analysis.bolt_plans),
        "repositories": list(affected_repositories(analysis)),
        "component_count": len(analysis.components),
        "contract_types": sorted({contract.type for contract in analysis.contracts}),
        "unknown_dependency_count": sum(1 for dependency in analysis.dependencies if dependency.status == "unknown"),
        "confidence": analysis.confidence,
        "approved": analysis.approval_state == "approved" and analysis.approved_revision == analysis.revision,
    }


def enterprise_review_evidence(analysis: ImpactAnalysis) -> tuple[str, ...]:
    """Return the enterprise review evidence type only for an approved current revision."""

    assert_approved(analysis)
    return ("approved-impact-analysis",)
