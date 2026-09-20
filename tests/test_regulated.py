import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from agora.identity import lifecycle_authorization_payload
from agora.model import (
    AddActorInput,
    ApplyLifecycleActionInput,
    AssignActorInput,
    ConfigureInput,
    CreateSwarmInput,
    CreateWorkInput,
    InitInput,
    InstallMethodInput,
    PrepareArtifactInput,
    PrepareCreateWorkInput,
    PrepareEvidenceInput,
)
from agora.workspace import AgoraWorkspace
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.provenance import parse
from agora_ai_sdlc.regulated import (
    CRITICAL_ACTIONS,
    EvidenceRetention,
    ExceptionRecord,
    RegulatedError,
    apply_signed_action,
    assess_assignments,
    assign_actor,
    evaluate_ai_execution,
    prepare_evidence,
    record_evidence_retention,
    record_exception,
    validate_exception,
    validate_retention,
)

NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)
PACK = asset_root("registry") / "methods" / "ai-sdlc"
BASE_ACTORS = {
    "product-owner": ("po", "human", ["specification"]),
    "architect": ("arch", "ai-agent", ["specification"]),
    "builder": ("build", "ai-agent", ["implementation"]),
    "operator": ("ops", "ai-agent", ["operations"]),
    "quality-reviewer": ("qa", "human", ["review"]),
}


def public_key(path: Path, private: Ed25519PrivateKey) -> Path:
    path.write_bytes(
        private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return path


@pytest.fixture
def regulated_workspace(tmp_path, monkeypatch):
    root, home = tmp_path / "project", tmp_path / "home"
    monkeypatch.setenv("AGORA_HOME", str(home))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    ws = AgoraWorkspace(cwd=root)
    ws.configure(ConfigureInput("generic", "local", "local", "scrum"))
    ws.initialize(InitInput())
    ws.install_method(InstallMethodInput(source=str(PACK), scope="project"))
    keys = {}
    for role, (actor_id, kind, capabilities) in BASE_ACTORS.items():
        private = Ed25519PrivateKey.generate()
        key_path = public_key(tmp_path / f"{actor_id}.pem", private)
        ws.add_actor(
            AddActorInput(
                id=actor_id,
                name=actor_id,
                kind=kind,
                capabilities=capabilities,
                scope="project",
                public_key=str(key_path),
                require_authentication=True,
            )
        )
        keys[actor_id] = private
    ws.create_swarm(CreateSwarmInput("delivery", "regulated", method="ai-sdlc", create_branch=False))
    for role, (actor_id, _kind, _capabilities) in BASE_ACTORS.items():
        assign_actor(ws, AssignActorInput("delivery", role, actor_id))
    return ws, keys, root


def sign(tmp_path: Path, private: Ed25519PrivateKey, action) -> str:
    path = tmp_path / f"{action.id}.sig"
    path.write_bytes(private.sign(lifecycle_authorization_payload(action)))
    return str(path)


def work(work_id: str = "feature") -> CreateWorkInput:
    return CreateWorkInput(
        swarm_id="delivery",
        id=work_id,
        title="Regulated change",
        actor_id="po",
        acceptance_criteria=[("value", "Delivers value")],
    )


def exception(**changes) -> ExceptionRecord:
    values = {
        "id": "temporary-control",
        "policy": "operational-control",
        "reason": "Compensating manual review is active",
        "authorized_by": "project:governance",
        "authorized_role": "governance-owner",
        "created_at": "2026-09-20T11:00:00Z",
        "expires_at": "2026-09-21T11:00:00Z",
        "evidence": "repo://evidence/approval-17",
    }
    values.update(changes)
    return ExceptionRecord(**values)


def retention(**changes) -> EvidenceRetention:
    values = {
        "id": "test-evidence",
        "evidence_ref": "test-evidence",
        "owner": "project:quality-reviewer",
        "classification": "internal",
        "policy": "quality-evidence-7-years",
        "recorded_at": "2026-09-20T11:00:00Z",
        "retain_until": "2033-09-20T11:00:00Z",
        "disposition": "review",
    }
    values.update(changes)
    return EvidenceRetention(**values)


def provenance(source: str = "observed", **changes):
    record = {
        "schema": "agora-ai-sdlc/provenance/v1",
        "actor": "project:builder",
        "runtime": {"value": "runner", "source": source},
        "runtime_version": {"value": "1.2.3", "source": source},
        "provider": {"value": "provider", "source": source},
        "model": {"value": "model", "source": source},
        "selection_reason": {"value": "approved-route", "source": source},
        "fallback": {"source": source, "used": False},
    }
    record.update(changes)
    return parse(record)


def test_profile_declares_regulated_composition_and_non_waivable_controls():
    profile = yaml.safe_load((asset_root("profiles") / "regulated" / "profile.yaml").read_text())
    assert profile["depth"] == "regulated" and profile["signed_actions"]["authority"] == "agora-core"
    assert set(profile["critical_actions"]) == CRITICAL_ACTIONS
    assert profile["mandatory_human_roles"] == ["product-owner", "quality-reviewer"]
    assert set(profile["non_waivable_controls"]) == {
        "signed-actions",
        "role-segregation",
        "mandatory-human-approval",
        "complete-observed-provenance",
    }


def test_unsigned_critical_mutation_rejected_and_valid_signature_is_audited(regulated_workspace, tmp_path):
    ws, keys, _root = regulated_workspace
    with pytest.raises(PermissionError, match="signed lifecycle action"):
        ws.create_work(work())
    action = ws.prepare_create_work(PrepareCreateWorkInput("create-feature", work()))
    with pytest.raises(PermissionError, match="signed lifecycle authorization"):
        ws.apply_lifecycle_action(ApplyLifecycleActionInput(action.id))
    applied = apply_signed_action(ws, action.id, sign(tmp_path, keys["po"], action))
    assert applied.status == "applied" and applied.authentication_verified
    assert applied.authentication_fingerprint and applied.authorization_sha256


def test_core_rejects_signed_action_after_precondition_becomes_stale(regulated_workspace, tmp_path):
    ws, keys, _root = regulated_workspace
    creation = ws.prepare_create_work(PrepareCreateWorkInput("create-work", work()))
    apply_signed_action(ws, creation.id, sign(tmp_path, keys["po"], creation))
    (ws.project_root() / "first.md").write_text("# first\n", encoding="utf-8")
    (ws.project_root() / "stale.md").write_text("# stale\n", encoding="utf-8")
    first = ws.prepare_add_artifact(
        PrepareArtifactInput("delivery", "feature", "po", "intent", "repo://first.md", id="add-first")
    )
    stale = ws.prepare_add_artifact(
        PrepareArtifactInput("delivery", "feature", "po", "intent", "repo://stale.md", id="add-stale")
    )
    apply_signed_action(ws, first.id, sign(tmp_path, keys["po"], first))
    with pytest.raises(ValueError, match="precondition"):
        apply_signed_action(ws, stale.id, sign(tmp_path, keys["po"], stale))


def test_assignment_preflight_requires_humans_and_active_signing_identity(tmp_path, monkeypatch):
    root, home = tmp_path / "project", tmp_path / "home"
    monkeypatch.setenv("AGORA_HOME", str(home))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    ws = AgoraWorkspace(cwd=root)
    ws.configure(ConfigureInput("generic", "local", "local", "scrum"))
    ws.initialize(InitInput())
    ws.install_method(InstallMethodInput(source=str(PACK), scope="project"))
    ws.add_actor(AddActorInput("robot", "robot", "ai-agent", ["specification"], "project"))
    ws.create_swarm(CreateSwarmInput("delivery", "regulated", method="ai-sdlc", create_branch=False))
    decision = assess_assignments(ws, "delivery", AssignActorInput("delivery", "product-owner", "robot"))
    assert not decision["allowed"]
    assert {item["code"] for item in decision["blockers"]} == {
        "regulated.assignment.human",
        "regulated.assignment.signature",
    }
    with pytest.raises(RegulatedError) as error:
        assign_actor(ws, AssignActorInput("delivery", "product-owner", "robot"))
    assert error.value.code == "regulated.assignment.human"
    assert ws.show_swarm("delivery").assignments == {}
    current = assess_assignments(ws, "delivery")
    assert not current["allowed"] and current["blockers"][0]["code"] == "regulated.assignment.incomplete"


def test_prohibited_role_combination_is_rejected_before_assignment(regulated_workspace):
    ws, _keys, _root = regulated_workspace
    # Use a fresh swarm and one human actor with every relevant capability.
    private = Ed25519PrivateKey.generate()
    key = public_key(Path(ws.project_root()) / "shared.pem", private)
    ws.add_actor(
        AddActorInput(
            "shared",
            "shared",
            "human",
            ["implementation", "review"],
            "project",
            public_key=str(key),
            require_authentication=True,
        )
    )
    ws.create_swarm(CreateSwarmInput("conflict", "regulated", method="ai-sdlc", create_branch=False))
    assign_actor(ws, AssignActorInput("conflict", "builder", "shared"))
    with pytest.raises(RegulatedError) as error:
        assign_actor(ws, AssignActorInput("conflict", "quality-reviewer", "shared"))
    assert error.value.code == "regulated.assignment.segregation"
    assert ws.show_swarm("conflict").assignments == {"builder": "project:shared"}


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"authorized_by": "project:unknown"}, "regulated.exception.authority"),
        ({"expires_at": "2026-09-20T12:00:00Z"}, "regulated.exception.expired"),
        ({"expires_at": "2026-11-01T11:00:00Z"}, "regulated.exception.time"),
        ({"policy": "role-segregation"}, "regulated.exception.policy"),
        ({"reason": "Bearer abcdefghijklmnop"}, "regulated.record.secret"),
    ],
)
def test_exception_rejects_unauthorized_expired_long_nonwaivable_or_secret(changes, code):
    with pytest.raises(RegulatedError) as error:
        validate_exception(
            exception(**changes),
            authorizers={"project:governance": "governance-owner"},
            now=NOW,
        )
    assert error.value.code == code


def test_exception_record_is_explicit_authorized_time_bound_and_immutable(tmp_path):
    record = exception()
    path = record_exception(
        tmp_path,
        record,
        authorizers={"project:governance": "governance-owner"},
        now=NOW,
    )
    saved = json.loads(path.read_text())
    assert saved["schema"] == "agora-ai-sdlc/regulated-audit/v1"
    assert saved["kind"] == "exception" and saved["expires_at"] == "2026-09-21T11:00:00Z"
    with pytest.raises(RegulatedError) as error:
        record_exception(
            tmp_path,
            record,
            authorizers={"project:governance": "governance-owner"},
            now=NOW,
        )
    assert error.value.code == "regulated.audit.immutable"


def test_audit_directory_cannot_escape_project_through_symlink(tmp_path):
    outside = tmp_path / "outside"
    project = tmp_path / "project"
    outside.mkdir()
    (project / ".agora").mkdir(parents=True)
    os.symlink(outside, project / ".agora" / "regulated")
    with pytest.raises(RegulatedError) as error:
        record_exception(
            project,
            exception(),
            authorizers={"project:governance": "governance-owner"},
            now=NOW,
        )
    assert error.value.code == "regulated.audit.path"
    assert not list(outside.iterdir())


def test_retention_metadata_is_current_complete_and_immutable(tmp_path):
    validated = validate_retention(retention(), now=NOW)
    assert validated["classification"] == "internal" and validated["disposition"] == "review"
    path = record_evidence_retention(tmp_path, retention(), now=NOW)
    assert json.loads(path.read_text())["evidence_ref"] == "test-evidence"
    with pytest.raises(RegulatedError) as error:
        record_evidence_retention(tmp_path, retention(), now=NOW)
    assert error.value.code == "regulated.audit.immutable"


def test_evidence_preparation_requires_bound_retention_metadata(regulated_workspace, tmp_path):
    ws, keys, root = regulated_workspace
    creation = ws.prepare_create_work(PrepareCreateWorkInput("create-work", work()))
    apply_signed_action(ws, creation.id, sign(tmp_path, keys["po"], creation))
    data = PrepareEvidenceInput(
        swarm_id="delivery",
        work_id="feature",
        actor_id="qa",
        type="test-suite",
        result="failure",
        id="add-test-evidence",
    )
    with pytest.raises(RegulatedError) as error:
        prepare_evidence(ws, data, retention(evidence_ref="different"), now=NOW)
    assert error.value.code == "regulated.retention.evidence"
    assert not (root / ".agora" / "actions" / data.id).exists()

    action = prepare_evidence(ws, data, retention(evidence_ref=data.id), now=NOW)
    audit = root / ".agora" / "regulated" / "evidence-retention" / "test-evidence.json"
    assert action.status == "prepared" and json.loads(audit.read_text())["evidence_ref"] == data.id
    with pytest.raises(PermissionError, match="signed lifecycle authorization"):
        ws.apply_lifecycle_action(ApplyLifecycleActionInput(action.id))


@pytest.mark.parametrize(
    "changes",
    [
        {"retain_until": "2026-09-20T12:00:00Z"},
        {"recorded_at": "2026-09-20T13:00:00Z"},
        {"classification": "unknown"},
        {"disposition": "ignore"},
    ],
)
def test_invalid_retention_metadata_fails_closed(changes):
    with pytest.raises(RegulatedError):
        validate_retention(retention(**changes), now=NOW)


def test_audit_validation_rejects_ambiguous_local_evaluation_time():
    with pytest.raises(RegulatedError) as error:
        validate_retention(retention(), now=datetime(2026, 9, 20, 12))  # noqa: DTZ001
    assert error.value.code == "regulated.record.time"


def test_ai_execution_requires_complete_observed_provenance():
    assert evaluate_ai_execution(provenance())["allowed"]
    declared = evaluate_ai_execution(provenance("declared"))
    assert not declared["allowed"] and len(declared["blockers"]) == 6


def test_ai_execution_rejects_one_missing_field_or_unobserved_fallback():
    missing = provenance(runtime_version={"source": "unavailable"})
    result = evaluate_ai_execution(missing)
    assert not result["allowed"] and "runtime_version" in result["blockers"][0]["message"]
    fallback = provenance(fallback={"source": "declared", "used": False})
    assert not evaluate_ai_execution(fallback)["allowed"]
