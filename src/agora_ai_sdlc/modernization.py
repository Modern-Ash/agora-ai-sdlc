"""Incremental modernization obligations over supported Agora Core records."""

import hashlib
import re

import yaml
from agora.model import TransitionWorkInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.artifacts import Artifact, ArtifactError, check_traceability, parse_artifact
from agora_ai_sdlc.depth_profiles import asset_root

PROFILE_SCHEMA = "agora-ai-sdlc/adoption-profile/v1"
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
FORWARD_GATES = {
    ("readiness", "intent"): "readiness-approved",
    ("intent", "inception"): "intent-framed",
    ("inception", "construction"): "architecture-approved",
    ("construction", "operations"): "build-verified",
    ("operations", "completed"): "completion",
}
PROFILE_KINDS = {
    "legacy-inventory",
    "dependency-map",
    "characterization",
    "target-architecture",
    "migration-plan",
    "migration-slice",
    "conversion-record",
    "equivalence-report",
    "cutover-plan",
    "stabilization-report",
}


class ModernizationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def load_profile() -> dict:
    path = asset_root("profiles") / "modernization" / "profile.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA or data.get("id") != "modernization":
        raise ModernizationError("modernization.profile.invalid", "invalid Modernization profile")
    if data.get("strategy") != "incremental-slices" or not isinstance(data.get("gate_obligations"), dict):
        raise ModernizationError("modernization.profile.strategy", "Modernization must use incremental slices")
    return data


def _strings(value: object, field: str, *, nonempty: bool = True) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or (nonempty and not value)
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ModernizationError("modernization.artifact.field", f"{field} must be a string list")
    if len(value) != len(set(value)):
        raise ModernizationError("modernization.artifact.field", f"{field} must not contain duplicates")
    return tuple(value)


def _slug(value: object, field: str) -> str:
    if not isinstance(value, str) or SLUG.fullmatch(value) is None:
        raise ModernizationError("modernization.artifact.field", f"{field} must be a slug")
    return value


def _one(artifacts: list[Artifact], kind: str) -> Artifact:
    matches = [artifact for artifact in artifacts if artifact.kind == kind]
    if len(matches) != 1:
        raise ModernizationError("modernization.artifact.cardinality", f"expected exactly one {kind}")
    return matches[0]


def _behaviors(characterization: Artifact) -> dict[str, dict]:
    raw = characterization.front.get("behaviors")
    if not isinstance(raw, list) or not raw:
        raise ModernizationError("modernization.behavior.missing", "characterization requires behaviors")
    behaviors: dict[str, dict] = {}
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"id", "status", "baseline", "evidence", "reason"}:
            raise ModernizationError("modernization.behavior.fields", "behavior fields are invalid")
        id_ = _slug(item["id"], "behavior id")
        if id_ in behaviors:
            raise ModernizationError("modernization.behavior.duplicate", f"duplicate behavior {id_}")
        status = item["status"]
        evidence = _strings(item["evidence"], "behavior evidence", nonempty=False)
        baseline, reason = item["baseline"], item["reason"]
        if status == "known":
            if not isinstance(baseline, str) or not baseline.strip() or not evidence or reason is not None:
                raise ModernizationError(
                    "modernization.behavior.known", f"known behavior {id_} requires baseline evidence"
                )
        elif status == "unknown":
            if baseline is not None or evidence or not isinstance(reason, str) or not reason.strip():
                raise ModernizationError(
                    "modernization.behavior.unknown", f"unknown behavior {id_} must record a reason without baseline"
                )
        else:
            raise ModernizationError("modernization.behavior.status", f"unsupported behavior status for {id_}")
        behaviors[id_] = item
    return behaviors


def _slices(artifacts: list[Artifact], plan: Artifact) -> dict[str, Artifact]:
    records = [artifact for artifact in artifacts if artifact.kind == "migration-slice"]
    if not records:
        raise ModernizationError("modernization.slice.missing", "migration plan requires at least one slice")
    slices: dict[str, Artifact] = {}
    for artifact in records:
        slice_id = _slug(artifact.front.get("slice-id"), "slice id")
        if slice_id in slices:
            raise ModernizationError("modernization.slice.duplicate", f"duplicate slice {slice_id}")
        if artifact.front.get("independently-deployable") is not True:
            raise ModernizationError(
                "modernization.slice.big_bang", f"slice {slice_id} is not independently deployable"
            )
        _strings(artifact.front.get("source-components"), "source components")
        _strings(artifact.front.get("target-components"), "target components")
        _strings(artifact.front.get("dependencies", []), "slice dependencies", nonempty=False)
        _strings(artifact.front.get("behavior-ids"), "slice behavior ids")
        if plan.id not in artifact.traces_to:
            raise ModernizationError("modernization.slice.trace", f"slice {slice_id} does not trace to {plan.id}")
        slices[slice_id] = artifact
    planned = set(_strings(plan.front.get("slice-ids"), "migration plan slice ids"))
    if planned != set(slices):
        raise ModernizationError("modernization.slice.plan", "migration plan and registered slice ids differ")
    return slices


def _by_slice(artifacts: list[Artifact], kind: str) -> dict[str, Artifact]:
    result: dict[str, Artifact] = {}
    for artifact in artifacts:
        if artifact.kind == kind:
            result[_slug(artifact.front.get("slice-id"), f"{kind} slice id")] = artifact
    return result


def _equivalence_blockers(
    behaviors: dict[str, dict], slices: dict[str, Artifact], artifacts: list[Artifact]
) -> list[dict]:
    blockers: list[dict] = []
    conversions = _by_slice(artifacts, "conversion-record")
    reports = _by_slice(artifacts, "equivalence-report")
    covered_behaviors = {
        behavior_id
        for artifact in slices.values()
        for behavior_id in _strings(artifact.front.get("behavior-ids"), "slice behavior ids")
    }
    if covered_behaviors != set(behaviors):
        blockers.append(
            _blocker("modernization.slice.coverage", "slice behavior coverage differs from characterization")
        )
    for slice_id, slice_artifact in slices.items():
        scoped_behaviors = set(_strings(slice_artifact.front.get("behavior-ids"), "slice behavior ids"))
        conversion = conversions.get(slice_id)
        report = reports.get(slice_id)
        if conversion is None or slice_artifact.id not in conversion.traces_to:
            blockers.append(_blocker("modernization.slice.conversion", "slice lacks traced conversion", slice=slice_id))
        if report is None or slice_artifact.id not in report.traces_to:
            blockers.append(
                _blocker("modernization.slice.equivalence", "slice lacks traced equivalence", slice=slice_id)
            )
            continue
        raw = report.front.get("comparisons")
        if not isinstance(raw, list):
            blockers.append(_blocker("modernization.equivalence.fields", "comparisons must be a list", slice=slice_id))
            continue
        comparisons: dict[str, dict] = {}
        for item in raw:
            if not isinstance(item, dict) or set(item) != {
                "behavior",
                "result",
                "evidence",
                "explanation",
                "accepted-by",
            }:
                blockers.append(
                    _blocker("modernization.equivalence.fields", "comparison fields are invalid", slice=slice_id)
                )
                continue
            try:
                behavior = _slug(item["behavior"], "comparison behavior")
            except ModernizationError as error:
                blockers.append(_blocker(error.code, str(error), slice=slice_id))
                continue
            if behavior in comparisons:
                blockers.append(
                    _blocker("modernization.equivalence.duplicate", "duplicate behavior comparison", slice=slice_id)
                )
            comparisons[behavior] = item
        for behavior_id in sorted(scoped_behaviors):
            behavior = behaviors.get(behavior_id)
            if behavior is None:
                blockers.append(
                    _blocker(
                        "modernization.slice.behavior",
                        "slice references undeclared behavior",
                        slice=slice_id,
                        behavior=behavior_id,
                    )
                )
                continue
            comparison = comparisons.get(behavior_id)
            if comparison is None:
                blockers.append(
                    _blocker(
                        "modernization.equivalence.missing",
                        "behavior is not compared",
                        slice=slice_id,
                        behavior=behavior_id,
                    )
                )
                continue
            result = comparison["result"]
            evidence = comparison["evidence"]
            explanation = comparison["explanation"]
            accepted_by = comparison["accepted-by"]
            if behavior["status"] == "unknown" and result == "equivalent":
                blockers.append(
                    _blocker(
                        "modernization.equivalence.invented",
                        "unknown behavior cannot be declared equivalent",
                        slice=slice_id,
                        behavior=behavior_id,
                    )
                )
            elif result == "equivalent":
                if not isinstance(evidence, list) or not evidence:
                    blockers.append(
                        _blocker(
                            "modernization.equivalence.evidence",
                            "equivalence requires evidence",
                            slice=slice_id,
                            behavior=behavior_id,
                        )
                    )
            elif result == "accepted-difference":
                if (
                    not isinstance(evidence, list)
                    or not evidence
                    or not isinstance(explanation, str)
                    or not explanation.strip()
                    or accepted_by != "product-owner"
                ):
                    blockers.append(
                        _blocker(
                            "modernization.equivalence.acceptance",
                            "accepted difference requires evidence, explanation and approver",
                            slice=slice_id,
                            behavior=behavior_id,
                        )
                    )
            else:
                blockers.append(
                    _blocker(
                        "modernization.equivalence.regression",
                        "behavior is regressed or unresolved",
                        slice=slice_id,
                        behavior=behavior_id,
                    )
                )
        unknown = sorted(set(comparisons) - scoped_behaviors)
        if unknown:
            blockers.append(
                _blocker(
                    "modernization.equivalence.unknown",
                    "report compares undeclared behavior",
                    slice=slice_id,
                    behaviors=tuple(unknown),
                )
            )
    extra = sorted((set(conversions) | set(reports)) - set(slices))
    if extra:
        blockers.append(
            _blocker("modernization.slice.unknown", "records reference unknown slices", slices=tuple(extra))
        )
    return blockers


def _blocker(code: str, message: str, **fields) -> dict:
    return {"code": code, "message": message, **fields}


def assess_documents(
    artifacts: list[Artifact],
    successful_evidence: set[str],
    gate: str,
    *,
    registered_kinds: set[str] | None = None,
) -> dict:
    profile = load_profile()
    obligations = profile["gate_obligations"].get(gate)
    if not isinstance(obligations, dict):
        raise ModernizationError("modernization.gate.unknown", f"unknown profile gate {gate}")
    kinds = registered_kinds if registered_kinds is not None else {artifact.kind for artifact in artifacts}
    blockers = [
        _blocker("modernization.gate.artifact", "required artifact is missing", artifact=kind)
        for kind in obligations["artifacts"]
        if kind not in kinds
    ]
    blockers.extend(
        _blocker("modernization.gate.evidence", "successful evidence is missing", evidence=kind)
        for kind in obligations["evidence"]
        if kind not in successful_evidence
    )
    try:
        check_traceability(artifacts)
    except ArtifactError as error:
        blockers.append(_blocker(error.code, str(error)))
    try:
        if gate in {"readiness-approved", "architecture-approved", "build-verified", "completion"}:
            characterization = _one(artifacts, "characterization")
            behaviors = _behaviors(characterization)
        if gate in {"architecture-approved", "build-verified", "completion"}:
            plan = _one(artifacts, "migration-plan")
            slices = _slices(artifacts, plan)
        if gate in {"build-verified", "completion"}:
            blockers.extend(_equivalence_blockers(behaviors, slices, artifacts))
        if gate == "completion":
            cutover = _one(artifacts, "cutover-plan")
            stabilization = _one(artifacts, "stabilization-report")
            expected = set(slices)
            if set(_strings(cutover.front.get("slice-ids"), "cutover slice ids")) != expected:
                blockers.append(_blocker("modernization.cutover.slices", "cutover does not cover every slice"))
            current_reports = {artifact.id for artifact in _by_slice(artifacts, "equivalence-report").values()}
            if not current_reports <= set(cutover.traces_to):
                blockers.append(
                    _blocker("modernization.cutover.trace", "cutover does not trace to equivalence reports")
                )
            if set(_strings(stabilization.front.get("slice-ids"), "stabilization slice ids")) != expected:
                blockers.append(
                    _blocker("modernization.stabilization.slices", "stabilization does not cover every slice")
                )
            if cutover.id not in stabilization.traces_to:
                blockers.append(
                    _blocker("modernization.stabilization.trace", "stabilization does not trace to cutover")
                )
    except ModernizationError as error:
        blockers.append(_blocker(error.code, str(error)))
    return {"profile": "modernization", "gate": gate, "allowed": not blockers, "blockers": tuple(blockers)}


def _workspace_documents(
    workspace: AgoraWorkspace, swarm_id: str, work_id: str
) -> tuple[list[Artifact], set[str], dict[str, str]]:
    root = workspace.project_root()
    documents = []
    uris: dict[str, str] = {}
    records = workspace.list_work_artifacts(swarm_id, work_id)
    for record in records:
        if record.kind not in PROFILE_KINDS:
            continue
        if not record.uri.startswith("repo://"):
            raise ModernizationError("modernization.artifact.uri", "profile artifacts must use repo:// URIs")
        path = root / record.uri.removeprefix("repo://")
        contents = path.read_bytes()
        if record.content_sha256 is not None and hashlib.sha256(contents).hexdigest() != record.content_sha256:
            raise ModernizationError("modernization.artifact.digest", f"registered artifact changed: {record.kind}")
        try:
            artifact = parse_artifact(contents.decode("utf-8"))
        except (UnicodeDecodeError, ArtifactError) as error:
            raise ModernizationError("modernization.artifact.invalid", f"invalid {record.kind} artifact") from error
        if artifact.kind != record.kind:
            raise ModernizationError("modernization.artifact.kind", "registered kind does not match document")
        documents.append(artifact)
        uris[artifact.id] = record.uri
    return documents, {record.kind for record in records}, uris


def assess_gate(workspace: AgoraWorkspace, swarm_id: str, work_id: str, gate: str) -> dict:
    try:
        documents, registered_kinds, document_uris = _workspace_documents(workspace, swarm_id, work_id)
        artifact_records = workspace.list_work_artifacts(swarm_id, work_id)
        evidence_records = workspace.list_work_evidence(swarm_id, work_id)
        evidence = {record.type for record in evidence_records if record.result == "success"}
        assessment = assess_documents(documents, evidence, gate, registered_kinds=registered_kinds)
        bindings = {
            "behavioral-equivalence": "equivalence-report",
            "cutover": "cutover-plan",
            "rollback-validation": "rollback-procedure",
            "stabilization": "stabilization-report",
        }
        required = load_profile()["gate_obligations"][gate]["evidence"]
        binding_blockers = []
        for evidence_type in required:
            expected_kind = bindings[evidence_type]
            if expected_kind == "equivalence-report":
                current_ids = {artifact.id for artifact in _by_slice(documents, expected_kind).values()}
                expected_uris = {document_uris[id_] for id_ in current_ids}
            else:
                expected_uris = {record.uri for record in artifact_records if record.kind == expected_kind}
            if not any(
                record.type == evidence_type
                and record.result == "success"
                and bool(expected_uris & set(record.artifact_references))
                for record in evidence_records
            ):
                binding_blockers.append(
                    _blocker(
                        "modernization.gate.evidence_binding",
                        "successful evidence is not bound to its required artifact",
                        evidence=evidence_type,
                        artifact=expected_kind,
                    )
                )
        if binding_blockers:
            return {
                **assessment,
                "allowed": False,
                "blockers": (*assessment["blockers"], *binding_blockers),
            }
        return assessment
    except ModernizationError as error:
        return {
            "profile": "modernization",
            "gate": gate,
            "allowed": False,
            "blockers": (_blocker(error.code, str(error)),),
        }


def require_gate(workspace: AgoraWorkspace, swarm_id: str, work_id: str, gate: str) -> dict:
    assessment = assess_gate(workspace, swarm_id, work_id, gate)
    if not assessment["allowed"]:
        codes = ", ".join(blocker["code"] for blocker in assessment["blockers"])
        raise ModernizationError("modernization.gate.blocked", f"{gate} blocked: {codes}")
    return assessment


def transition(workspace: AgoraWorkspace, data: TransitionWorkInput):
    work = workspace.show_work(data.swarm_id, data.work_id)
    gate = FORWARD_GATES.get((work.state, data.target_state))
    if gate is not None:
        require_gate(workspace, data.swarm_id, data.work_id, gate)
    return workspace.transition_work(data)
