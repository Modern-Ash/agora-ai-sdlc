import shutil
from pathlib import Path

import pytest
from agora.model import AddArtifactInput, AddEvidenceInput, TransitionWorkInput
from support.lifecycle import Lifecycle

from agora_ai_sdlc.artifacts import parse_artifact
from agora_ai_sdlc.modernization import (
    ModernizationError,
    assess_documents,
    assess_gate,
    load_profile,
    transition,
)

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "samples" / "modernization" / "fixtures"
PASSING = (
    "legacy-inventory",
    "dependency-map",
    "characterization",
    "target-architecture",
    "migration-plan",
    "migration-slice",
    "conversion-record",
    "equivalence-passed",
    "cutover-plan",
    "stabilization-report",
)


def document(name: str):
    return parse_artifact((FIXTURES / f"{name}.md").read_text(encoding="utf-8"))


def documents(*, equivalence: str = "equivalence-passed"):
    return [document(equivalence if name == "equivalence-passed" else name) for name in PASSING]


def replace_document(items, kind: str, text: str):
    return [parse_artifact(text) if item.kind == kind else item for item in items]


def blocker_codes(result):
    return {blocker["code"] for blocker in result["blockers"]}


def test_profile_composes_base_lifecycle_with_incremental_gate_obligations():
    profile = load_profile()
    assert profile["extends"] == "starter" and profile["method"] == {"id": "ai-sdlc", "version": "0.1.0"}
    assert profile["strategy"] == "incremental-slices"
    assert profile["gate_obligations"]["build-verified"]["evidence"] == ["behavioral-equivalence"]
    assert profile["gate_obligations"]["completion"]["evidence"] == [
        "cutover",
        "rollback-validation",
        "stabilization",
    ]


@pytest.mark.parametrize(
    ("gate", "evidence"),
    [
        ("readiness-approved", set()),
        ("architecture-approved", set()),
        ("build-verified", {"behavioral-equivalence"}),
        ("completion", {"behavioral-equivalence", "cutover", "rollback-validation", "stabilization"}),
    ],
)
def test_passing_documents_satisfy_each_profile_gate(gate, evidence):
    items = documents()
    kinds = {item.kind for item in items} | {"rollback-procedure"}
    result = assess_documents(items, evidence, gate, registered_kinds=kinds)
    assert result["allowed"] and result["blockers"] == ()


def test_unknown_behavior_is_recorded_without_invented_baseline():
    items = documents()
    source = (FIXTURES / "characterization.md").read_text(encoding="utf-8")
    invented = source.replace("baseline: null", 'baseline: "assumed zero"', 1)
    result = assess_documents(replace_document(items, "characterization", invented), set(), "readiness-approved")
    assert not result["allowed"]
    assert "modernization.behavior.unknown" in blocker_codes(result)


def test_failed_equivalence_and_unresolved_unknown_block_operations():
    result = assess_documents(
        documents(equivalence="equivalence-failed"),
        {"behavioral-equivalence"},
        "build-verified",
    )
    assert not result["allowed"]
    assert "modernization.equivalence.regression" in blocker_codes(result)


def test_accepted_difference_requires_evidence_explanation_and_approver():
    items = documents()
    source = (FIXTURES / "equivalence-passed.md").read_text(encoding="utf-8")
    invalid = source.replace("accepted-by: product-owner", "accepted-by: null")
    result = assess_documents(
        replace_document(items, "equivalence-report", invalid),
        {"behavioral-equivalence"},
        "build-verified",
    )
    assert "modernization.equivalence.acceptance" in blocker_codes(result)


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        ("independently-deployable: true", "independently-deployable: false", "modernization.slice.big_bang"),
        ("traces-to: [MGP-001]", "traces-to: []", "modernization.slice.trace"),
        ("slice-ids: [checkout-total]", "slice-ids: [different]", "modernization.slice.plan"),
    ],
)
def test_slice_must_be_independent_planned_and_traced(old, new, code):
    items = documents()
    if "independently" in old or "traces-to" in old:
        kind, name = "migration-slice", "migration-slice"
    else:
        kind, name = "migration-plan", "migration-plan"
    changed = (FIXTURES / f"{name}.md").read_text(encoding="utf-8").replace(old, new, 1)
    result = assess_documents(replace_document(items, kind, changed), set(), "architecture-approved")
    assert code in blocker_codes(result)


def test_each_slice_requires_traced_conversion_and_equivalence():
    items = [item for item in documents() if item.kind != "conversion-record"]
    result = assess_documents(items, {"behavioral-equivalence"}, "build-verified")
    assert "modernization.gate.artifact" in blocker_codes(result)
    assert "modernization.slice.conversion" in blocker_codes(result)


@pytest.mark.parametrize("missing", ["behavioral-equivalence", "cutover", "rollback-validation", "stabilization"])
def test_required_evidence_fails_closed(missing):
    gate = "build-verified" if missing == "behavioral-equivalence" else "completion"
    all_evidence = {"behavioral-equivalence", "cutover", "rollback-validation", "stabilization"}
    kinds = {item.kind for item in documents()} | {"rollback-procedure"}
    result = assess_documents(documents(), all_evidence - {missing}, gate, registered_kinds=kinds)
    assert not result["allowed"] and "modernization.gate.evidence" in blocker_codes(result)


def test_completion_requires_rollback_artifact_even_with_successful_evidence():
    evidence = {"behavioral-equivalence", "cutover", "rollback-validation", "stabilization"}
    result = assess_documents(documents(), evidence, "completion")
    assert not result["allowed"] and any(
        blocker.get("artifact") == "rollback-procedure" for blocker in result["blockers"]
    )


def test_registered_artifact_digest_drift_blocks_assessment(tmp_path, monkeypatch):
    life = Lifecycle(tmp_path / "project", tmp_path / "home", monkeypatch)
    destination = life.root / "characterization.md"
    shutil.copyfile(FIXTURES / "characterization.md", destination)
    life.ws.add_artifact(
        AddArtifactInput("delivery", "feature", "po", "characterization", "repo://characterization.md")
    )
    destination.write_text(destination.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    result = assess_gate(life.ws, "delivery", "feature", "readiness-approved")
    assert not result["allowed"] and blocker_codes(result) == {"modernization.artifact.digest"}


def test_successful_evidence_must_bind_to_equivalence_report(tmp_path, monkeypatch):
    life = Lifecycle(tmp_path / "project", tmp_path / "home", monkeypatch)
    actors = {
        "legacy-inventory": "po",
        "dependency-map": "po",
        "characterization": "po",
        "target-architecture": "arch",
        "migration-plan": "arch",
        "migration-slice": "arch",
        "conversion-record": "build",
        "equivalence-failed": "qa",
        "equivalence-passed": "qa",
    }
    uris = {}
    for name, actor in actors.items():
        source = FIXTURES / f"{name}.md"
        destination = life.root / source.name
        shutil.copyfile(source, destination)
        parsed = parse_artifact(destination.read_text(encoding="utf-8"))
        uri = f"repo://{source.name}"
        life.ws.add_artifact(AddArtifactInput("delivery", "feature", actor, parsed.kind, uri))
        uris[name] = uri
    life.ws.add_evidence(
        AddEvidenceInput(
            "delivery",
            "feature",
            "qa",
            "behavioral-equivalence",
            "success",
            [uris["equivalence-failed"]],
        )
    )
    result = assess_gate(life.ws, "delivery", "feature", "build-verified")
    assert not result["allowed"]
    assert "modernization.gate.evidence_binding" in blocker_codes(result)


def test_profile_transition_blocks_before_core_state_change(tmp_path, monkeypatch):
    life = Lifecycle(tmp_path / "project", tmp_path / "home", monkeypatch)
    life.artifact("po", "readiness-assessment")
    life.clarify()
    life.approve("po", "product-owner")
    with pytest.raises(ModernizationError) as error:
        transition(life.ws, TransitionWorkInput("delivery", "feature", "po", "intent"))
    assert error.value.code == "modernization.gate.blocked" and life.state() == "readiness"
