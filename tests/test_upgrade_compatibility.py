"""Upgrade compatibility: a released Method Pack change must not corrupt in-flight work."""

import shutil
import subprocess
import sys

import pytest
from agora.model import InstallMethodInput

from agora_ai_sdlc.scenario import PACK, Lifecycle


def _pack_copy(tmp_path, version, transform=lambda text: text):
    target = tmp_path / f"pack-{version}"
    shutil.copytree(PACK, target)
    method = target / "METHOD.md"
    text = transform(method.read_text(encoding="utf-8"))
    method.write_text(text.replace('version: "0.1.0"', f'version: "{version}"'), encoding="utf-8")
    return target


def _validate(project):
    return subprocess.run(
        [sys.executable, "-m", "agora", "validate"], cwd=project, capture_output=True, text=True, check=False
    )


@pytest.fixture
def in_flight(tmp_path):
    life = Lifecycle(tmp_path / "project", tmp_path / "home")
    life.to_intent()
    life.to_inception()
    life.to_construction()
    assert life.state() == "construction"
    return life


def test_compatible_pack_version_bump_keeps_in_flight_work_completable(in_flight, tmp_path):
    upgraded = _pack_copy(tmp_path, "0.1.1")

    record = in_flight.ws.install_method(InstallMethodInput(source=str(upgraded), scope="project", force=True))

    assert record.version == "0.1.1" and record.work_states[-1] == "completed"
    assert in_flight.state() == "construction"
    in_flight.to_operations()
    in_flight.to_completed()
    assert in_flight.state() == "completed"
    assert _validate(in_flight.root).returncode == 0


def test_installing_over_an_existing_pack_requires_explicit_force(in_flight, tmp_path):
    upgraded = _pack_copy(tmp_path, "0.1.1")

    with pytest.raises(FileExistsError, match="--force"):
        in_flight.ws.install_method(InstallMethodInput(source=str(upgraded), scope="project"))

    assert in_flight.state() == "construction"


def test_incompatible_pack_change_is_rejected_and_leaves_the_project_valid(in_flight, tmp_path):
    incompatible = _pack_copy(tmp_path, "0.2.0", lambda text: text.replace('"construction"', '"building"', 1))

    with pytest.raises(ValueError, match="uses a state not defined"):
        in_flight.ws.install_method(InstallMethodInput(source=str(incompatible), scope="project", force=True))

    assert in_flight.state() == "construction"
    assert _validate(in_flight.root).returncode == 0
    in_flight.to_operations()
    in_flight.to_completed()
    assert in_flight.state() == "completed"
