import json
from types import SimpleNamespace

import pytest

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_envelope import (
    STOP_OPERATION,
    CoreSnapshot,
    EnvelopeError,
    build_envelope,
    snapshot_from_workspace,
    validate_current,
    verify_integrity,
)
from agora_ai_sdlc.execution_requirements import requirements_for
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding


def make_bundle(next_action="inspect-next"):
    return ExecutionBundle(
        schema="s", swarm="delivery", work="issue-26", stage="construction", next_action=next_action, branch=None,
        base_branch=None, head=None, objective="o", acceptance_criteria=(), changed_paths=(), dirty_paths=(),
        related_paths=(), languages=(), build_systems=(), verification_commands=(), risks=(),
        governance={}, deterministic_inception_path=None,
    )  # fmt: skip


def snap(**over):
    base = {
        "swarm": "delivery", "work": "issue-26", "revision": "rev-4", "state": "construction",
        "target": "operations", "role": "builder", "assignments": {"builder": "project:developer"},
        "actors": frozenset({"project:developer"}), "human_boundary": False,
    }  # fmt: skip
    return CoreSnapshot(**{**base, **over})


CLAUDE = RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef("anthropic", "anthropic", "m1"))
REQ = requirements_for(make_bundle())


def build(binding=CLAUDE, snapshot=None, actor="project:developer", bundle=None, req=REQ):
    return build_envelope(snapshot or snap(), req, binding, bundle or make_bundle(), actor_id=actor)


def test_valid_developer_actor_with_claude_runtime_keeps_identities_separate():
    data = build().to_dict()
    assert data["authority"] == {"actor_id": "project:developer", "role": "builder", "human_boundary": False}
    assert data["runtime"]["agent"] == {"id": "claude", "integration": "claude-code"}
    assert data["next_transition"]["operation"] == "construction.execute"
    assert data["next_transition"]["arguments"] == [{"name": "work", "value": "issue-26"}]
    assert data["executable"] and "ai-claude" not in json.dumps(data)


def test_runtime_name_is_never_an_actor():
    with pytest.raises(EnvelopeError) as error:
        build(actor="ai-claude")
    assert error.value.code == "envelope.actor_missing"


def test_missing_and_unauthorized_actor():
    with pytest.raises(EnvelopeError) as error:
        build(actor="project:ghost")
    assert error.value.code == "envelope.actor_missing"
    other = snap(actors=frozenset({"project:developer", "project:reviewer"}))
    with pytest.raises(EnvelopeError) as error:
        build(snapshot=other, actor="project:reviewer")
    assert error.value.code == "envelope.actor_unauthorized"


def test_inadmissible_binding_fails_before_launch():
    bare = RuntimeBinding(AgentRuntimeRef("claude", "claude-code"))
    with pytest.raises(EnvelopeError) as error:
        build(binding=bare)
    assert error.value.code == "envelope.binding_inadmissible"


def test_revision_drift_and_new_gate_force_recalculation():
    envelope = build()
    assert validate_current(envelope, snap(), REQ).valid
    drift = validate_current(envelope, snap(revision="rev-5"), REQ)
    assert drift.reasons == ("envelope.stale_revision",) and drift.must_recalculate
    gate = validate_current(envelope, snap(human_boundary=True), REQ)
    assert "envelope.human_boundary_appeared" in gate.reasons
    revoked = validate_current(envelope, snap(assignments={"builder": "project:other"}), REQ)
    assert "envelope.actor_unauthorized" in revoked.reasons


def test_human_boundary_yields_stop_envelope_without_runtime():
    envelope = build(snapshot=snap(human_boundary=True))
    data = envelope.to_dict()
    assert not envelope.executable and data["runtime"] is None
    assert data["next_transition"]["operation"] == STOP_OPERATION and data["authority"]["human_boundary"]


def test_model_change_keeps_lifecycle_semantics():
    other = RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef("anthropic", "anthropic", "m2"))
    first, second = build().to_dict(), build(binding=other).to_dict()
    assert first["next_transition"] == second["next_transition"] and first["authority"] == second["authority"]
    assert first["digest"] != second["digest"]


def test_governed_transition_carries_ordered_typed_arguments():
    data = build(bundle=make_bundle("governed-transition")).to_dict()
    assert data["next_transition"] == {
        "operation": "lifecycle.transition",
        "arguments": [{"name": "work", "value": "issue-26"}, {"name": "target", "value": "operations"}],
    }
    assert data["display"] == "lifecycle.transition --work issue-26 --target operations"


def test_serialization_is_deterministic_and_round_trips():
    assert build().to_json() == build().to_json()
    payload = build().to_dict()
    assert verify_integrity(json.loads(json.dumps(payload))).to_dict() == payload


def test_adapter_tampering_is_rejected():
    payload = build().to_dict()
    altered = json.loads(json.dumps(payload))
    altered["next_transition"]["operation"] = "lifecycle.transition"
    with pytest.raises(EnvelopeError) as error:
        verify_integrity(altered)
    assert error.value.code == "envelope.tampered"
    added = json.loads(json.dumps(payload))
    added["next_transition"]["arguments"].append({"name": "approve", "value": "true"})
    with pytest.raises(EnvelopeError):
        verify_integrity(added)
    with pytest.raises(EnvelopeError) as error:
        verify_integrity({"schema": "x"})
    assert error.value.code == "envelope.malformed"


def test_snapshot_from_workspace_uses_core_facts():
    workspace = SimpleNamespace(
        show_swarm=lambda swarm: SimpleNamespace(assignments={"builder": "project:developer"}),
        work_inspection_read_set_sha256=lambda swarm, work: "abc",
        list_actors=lambda: [SimpleNamespace(reference="project:developer")],
    )
    status = SimpleNamespace(
        swarm="delivery", work="issue-26", state="construction", target="operations", role="builder",
        missing_approvals=(),
    )  # fmt: skip
    got = snapshot_from_workspace(workspace, status)
    assert got.revision == "abc" and got.actors == frozenset({"project:developer"}) and not got.human_boundary
