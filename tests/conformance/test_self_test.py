import json
import os
import shutil
from pathlib import Path

import pytest

from agora_ai_sdlc.conformance import RESULT_SCHEMA, run_self_test
from agora_ai_sdlc.conformance import self_test as harness

ROOT = Path(__file__).parents[2]


def _track_workspace(monkeypatch, tmp_path, name):
    workspace = tmp_path / name

    def create(*_args, **_kwargs):
        workspace.mkdir()
        return str(workspace)

    monkeypatch.setattr(harness, "mkdtemp", create)
    return workspace


def test_self_test_discovers_assets_exercises_roles_and_does_not_touch_caller(monkeypatch, tmp_path):
    workspace = _track_workspace(monkeypatch, tmp_path, "success")
    caller = tmp_path / "caller"
    caller.mkdir()
    marker = caller / "owned.txt"
    marker.write_text("unchanged\n", encoding="utf-8")
    monkeypatch.chdir(caller)
    monkeypatch.setenv("AGORA_HOME", "/original/home")

    result = run_self_test()

    assert result["schema"] == RESULT_SCHEMA and result["ok"]
    assert result["workspace"] is None and not workspace.exists()
    assert marker.read_text(encoding="utf-8") == "unchanged\n"
    assert sorted(caller.iterdir()) == [marker]
    assert os.environ["AGORA_HOME"] == "/original/home"
    assert set(result) == {"schema", "ok", "assets", "role_conformance", "checks", "failures", "workspace"}
    assert set(result["assets"]) == {"methods", "profiles", "policies", "templates", "contracts", "samples"}
    assert all(set(check) == {"id", "kind", "status"} for check in result["checks"])
    assert result["assets"]["methods"] == ["ai-sdlc"]
    assert result["assets"]["samples"] == sorted(path.parent.name for path in (ROOT / "samples").glob("*/run.py"))
    assert set(result["assets"]["profiles"]) >= {
        "depth/minimal",
        "depth/standard",
        "depth/comprehensive",
        "regulated",
        "starter",
        "enterprise",
        "modernization",
    }
    roles = result["role_conformance"]
    assert roles["final_state"] == "completed"
    assert roles["delegated_roles"] == ["architect", "builder"]
    assert roles["service_assignments_rejected"] == 5
    assert {check["status"] for check in result["checks"]} == {"passed"}


def test_injected_failure_is_structured_and_retains_reported_workspace(monkeypatch, tmp_path):
    workspace = _track_workspace(monkeypatch, tmp_path, "failed")
    result = run_self_test(_fail_check="roles")
    try:
        assert not result["ok"] and result["workspace"] == str(workspace)
        assert workspace.is_dir() and (workspace / "samples").is_dir()
        assert result["failures"] == [
            {"check": "roles", "type": "RuntimeError", "message": "injected failure at roles"}
        ]
        assert result["checks"][1] == {"id": "roles", "kind": "core-lifecycle", "status": "failed"}
        assert result["checks"][-1] == {"id": "sample:starter", "kind": "sample", "status": "passed"}
    finally:
        shutil.rmtree(workspace)


def test_interruption_cleans_workspace_and_restores_environment(monkeypatch, tmp_path):
    workspace = _track_workspace(monkeypatch, tmp_path, "interrupted")
    monkeypatch.setenv("AGORA_HOME", "/original/home")

    def interrupt_after_roles(message):
        if message.startswith("sample:"):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_self_test(progress=interrupt_after_roles)

    assert not workspace.exists()
    assert os.environ["AGORA_HOME"] == "/original/home"


def test_result_contract_and_checked_in_json_schema():
    schema = json.loads(
        (ROOT / "contracts" / "conformance" / "self-test-result-v1.schema.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema"]["const"] == RESULT_SCHEMA
    assert set(schema["required"]) == {"schema", "ok", "assets", "role_conformance", "checks", "failures", "workspace"}
