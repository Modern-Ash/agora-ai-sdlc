import tomllib
from pathlib import Path

from agora_ai_sdlc.doctor import DoctorCheck, render_doctor


def test_standard_package_declares_core_and_laya_as_direct_dependencies():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]

    assert any(item.startswith("agora-framework") for item in dependencies)
    assert any(item.startswith("laya") for item in dependencies)


def test_compatibility_extras_do_not_create_a_split_install_contract():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    extras = project["project"]["optional-dependencies"]

    assert extras["full"] == []
    assert extras["laya"] == []


def test_doctor_presents_internal_components_as_one_flow_environment():
    rendered = render_doctor(
        (
            DoctorCheck("core-kernel", True, "0.9.1 · internal governance kernel"),
            DoctorCheck("agora-flow", True, "0.3.0"),
            DoctorCheck("decision-plane", True, "Laya 0.3.20 · local System-1 available"),
        ),
        (),
    )

    assert "core-kernel" in rendered
    assert "agora-flow" in rendered
    assert "decision-plane" in rendered
    assert "install Core separately" not in rendered
