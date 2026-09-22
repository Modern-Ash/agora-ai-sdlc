import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from agora_ai_sdlc.skill_resources import PHASES, bundle, install_resources, resource_paths, resource_root


@pytest.mark.parametrize("phase", PHASES)
def test_progressive_bundle_has_root_and_only_one_phase(phase):
    result = bundle(phase, include_content=True)
    assert len(result["resources"]) == 2
    assert result["resources"][1]["path"] == f"references/{phase}.md"
    assert result["content_bytes"] == sum(len(r["content"].encode()) for r in result["resources"])
    root = result["resources"][0]["content"]
    assert "Never record a human approval without explicit confirmation" in root
    assert "assert_can_start" in root
    assert "Core remains lifecycle authority" in root
    assert "stderr" in root
    assert len(root.encode()) < 6000


def test_unknown_phase_cannot_read_arbitrary_paths():
    for phase in ("../secrets", "/tmp/key", "unknown"):
        with pytest.raises(ValueError, match="unknown-phase"):
            resource_paths(phase)


def test_install_copies_all_phase_resources_and_preserves_user_files(tmp_path):
    destination = tmp_path / "skill"
    destination.mkdir()
    (destination / "my-note.md").write_text("user content")
    path = install_resources(resource_root(), destination)
    assert path == destination / "SKILL.md"
    for phase in PHASES:
        assert (destination / "references" / f"{phase}.md").read_bytes() == resource_paths(phase)[1].read_bytes()
    assert (destination / "my-note.md").read_text() == "user content"
    first = {p: p.stat().st_mtime_ns for p in destination.rglob("*.md")}
    install_resources(resource_root(), destination)
    assert {p: p.stat().st_mtime_ns for p in first} == first


def test_install_rejects_symlink_before_any_write(tmp_path):
    destination = tmp_path / "skill"
    destination.mkdir()
    (destination / "references").symlink_to(tmp_path / "escape")
    with pytest.raises(ValueError, match="symlink"):
        install_resources(resource_root(), destination)
    assert not (destination / "SKILL.md").exists()


def test_wheel_contains_progressive_resources_and_loads_outside_repo(tmp_path):
    # Exercise installed asset discovery from the built wheel without a source-tree fallback.
    # Core-compat jobs intentionally install Core with plain pip and may not provide uv.
    if shutil.which("uv") is None:
        pytest.skip("uv is required only for the wheel packaging integration check")
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path / "dist"), "--quiet"],
        cwd=root,
        check=True,
        capture_output=True,
        env=env,
    )
    wheel = next((tmp_path / "dist").glob("*.whl"))
    installed = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(installed)
    env["PYTHONPATH"] = str(installed)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; sys.path.insert(0, sys.argv[1]); import json; "
                "from agora_ai_sdlc import skill_resources; "
                "assert str(skill_resources.__file__).startswith(sys.argv[1]); "
                "print(json.dumps(skill_resources.bundle('review')))"
            ),
            str(installed),
        ],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    built = json.loads(result.stdout)
    assert built == bundle("review")
