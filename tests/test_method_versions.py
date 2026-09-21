import subprocess
import sys
from pathlib import Path

import pytest
from agora.methods import load_method_contract

from agora_ai_sdlc.method_versions import (
    DEFAULT_CANDIDATE_VERSION,
    DEFAULT_METHOD_VERSION,
    MethodVersionError,
    method_pack_path,
)
from agora_ai_sdlc.scenario import Lifecycle

ROOT = Path(__file__).parent.parent


def test_version_paths_are_explicit_and_preserve_010():
    assert DEFAULT_METHOD_VERSION == "0.1.0"
    assert DEFAULT_CANDIDATE_VERSION == "0.2.0"
    assert method_pack_path("0.1.0") == ROOT / "registry" / "methods" / "ai-sdlc"
    assert method_pack_path("0.2.0") == ROOT / "registry" / "method-versions" / "ai-sdlc" / "0.2.0"


def test_unknown_version_fails_closed():
    with pytest.raises(MethodVersionError) as exc:
        method_pack_path("0.3.0")
    assert exc.value.code == "method.version_unknown"


def test_020_contract_is_three_phase_with_minimal_roles():
    contract = load_method_contract(method_pack_path("0.2.0"))

    assert contract.version == "0.2.0"
    assert contract.work_states == ["inception", "construction", "operations", "completed"]
    assert contract.terminal_state == "completed"
    assert contract.required_roles == ["product-owner", "developer"]
    assert contract.optional_roles == ["quality-reviewer"]
    assert {(rule.source, rule.target, rule.gate) for rule in contract.transitions} == {
        ("inception", "construction", "inception-approved"),
        ("construction", "inception", None),
        ("construction", "operations", "construction-verified"),
        ("operations", "construction", None),
        ("operations", "completed", "completion"),
    }


@pytest.mark.parametrize("version", ["0.1.0", "0.2.0"])
def test_both_versions_install_and_validate_with_core(tmp_path, version):
    project = tmp_path / version.replace(".", "-")
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)

    def agora(*args):
        return subprocess.run(
            [sys.executable, "-m", "agora", *args],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )

    assert agora("init", "--path", ".").returncode == 0
    installed = agora("method", "install", "--source", str(method_pack_path(version)), "--scope", "project")
    assert installed.returncode == 0, installed.stderr
    validated = agora("validate")
    assert validated.returncode == 0, validated.stderr


def test_lifecycle_default_remains_010_and_candidate_starts_in_inception(tmp_path):
    current = Lifecycle(tmp_path / "current", tmp_path / "home-current")
    candidate = Lifecycle(tmp_path / "candidate", tmp_path / "home-candidate", method_version="0.2.0")

    assert current.method_version == "0.1.0"
    assert current.state() == "readiness"
    assert candidate.method_version == "0.2.0"
    assert candidate.state() == "inception"
