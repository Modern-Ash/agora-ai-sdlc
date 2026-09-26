import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from support import runtime_scenarios as sc

from agora_ai_sdlc.cli import main
from agora_ai_sdlc.runtime_adapter import sync_projection
from agora_ai_sdlc.runtime_diagnostics import diagnose, preview_migration, render_diagnostics


def project(root, runtimes):
    (root / "ai-sdlc").mkdir()
    (root / "ai-sdlc" / "project.yaml").write_text(yaml.safe_dump({"schema": "x", "runtimes": runtimes}))


def snapshot_tree(root):
    return {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}


LEGACY = [
    {"id": "opencode", "integration": "opencode", "provider": "ollama", "model": "qwen2.5-coder:7b"},
    {"id": "claude", "integration": "claude", "provider": "anthropic", "model": "claude-sonnet-x"},
]


def test_migration_preview_is_deterministic_never_writes_and_flags_ambiguity(tmp_path):
    project(tmp_path, [*LEGACY, {"id": "ollama", "integration": "generic", "provider": "ollama", "model": "q"}])
    before = snapshot_tree(tmp_path)
    first = preview_migration(tmp_path)
    assert first == preview_migration(tmp_path) and snapshot_tree(tmp_path) == before
    assert first["writes"] is False and first["ambiguous"] == 1
    ok, _, bad = first["records"]
    assert (
        ok["to"]["agent"] == {"id": "opencode", "integration": "opencode"} and ok["to"]["model"]["provider"] == "ollama"
    )
    assert bad["diagnostic"]["code"] == "runtime.legacy_model_runtime_as_agent" and "to" not in bad


def test_cli_migrate_preview_and_diagnose(tmp_path, capsys):
    project(tmp_path, LEGACY)
    assert main(["runtimes", "--migrate-preview", "--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["records"][0]["to"]["schema"].endswith("runtime-binding/v2")
    assert main(["runtimes", "--diagnose", "--root", str(tmp_path)]) == 0
    assert "Agent runtime:" in capsys.readouterr().out


def test_diagnostics_show_binding_status_projection_and_laya(tmp_path):
    project(tmp_path, LEGACY[:1])
    found = sc.observed()
    report = diagnose(tmp_path, availability=found, laya_available=lambda: True)
    item = report["runtimes"][0]
    assert item["binding_status"] == "eligible" and item["adapter"] == "opencode" and item["projection"] == "drifted"
    assert item["model_runtime"] == "ollama" and item["model"] == "qwen2.5-coder:7b"
    assert "workspace.write" in item["agent_capabilities"] and report["laya"] == "available (advisory only)"
    adapter = sc.adapters(tmp_path)["opencode-ollama"]
    sync_projection(tmp_path, adapter.plan_projection(()))
    assert diagnose(tmp_path, availability=found)["runtimes"][0]["projection"] == "in sync"
    text = render_diagnostics(diagnose(tmp_path, availability=found, laya_available=lambda: False))
    assert "Binding status: eligible" in text and "Projection: in sync" in text and "unavailable" in text


def test_diagnostics_report_blocked_binding_without_secrets(tmp_path):
    project(tmp_path, LEGACY[:1])
    report = diagnose(tmp_path, availability=sc.observed(ollama_models=("other:1",)))
    item = report["runtimes"][0]
    assert item["binding_status"] == "blocked" and item["blockers"] == ["runtime.model_unavailable"]
    assert "sk-" not in json.dumps(report)
