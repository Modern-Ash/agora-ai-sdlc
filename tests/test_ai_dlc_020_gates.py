from pathlib import Path

from agora.markdown import read_markdown

from agora_ai_sdlc.method_versions import method_pack_path


def front(path: Path) -> dict:
    return read_markdown(path).attributes


def test_ai_dlc_020_inception_gate_requires_method_outputs():
    gate = front(method_pack_path("0.2.0") / "gates" / "inception-approved.md")
    assert set(gate["required-artifacts"]) == {
        "intent",
        "plan",
        "requirements",
        "user-stories",
        "nfr",
        "risk-register",
        "measurement-criteria",
        "unit-of-work",
        "bolt-plan",
    }
    assert gate["required-criterion-stage"] == "elaborated"
    assert set(gate["required-approval-roles"]) == {"product-owner", "developer"}
    assert gate["require-resolved-clarifications"] is True


def test_ai_dlc_020_construction_gate_requires_semantic_design_and_deployment_unit():
    gate = front(method_pack_path("0.2.0") / "gates" / "construction-verified.md")
    assert set(gate["required-artifacts"]) == {
        "domain-model",
        "logical-design",
        "implementation-plan",
        "test-strategy",
        "deployment-unit",
    }
    assert gate["required-criterion-stage"] == "verified"
    assert gate["required-evidence-types"] == ["test-suite"]
