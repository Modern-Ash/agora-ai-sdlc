import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def load_sample(name):
    path = ROOT / "samples" / name / "run.py"
    spec = importlib.util.spec_from_file_location(f"sample_{name.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["gitlab-delivery", "jira-work-items"])
def test_follow_on_sample_completes_offline(name, capsys):
    summary = load_sample(name).main()
    capsys.readouterr()
    assert summary["final_state"] == "completed"
    assert summary["validate"] == "ok"
    assert summary["profile_mode"] == "read-only"
    assert summary["idempotent_reconciliation"]
    assert summary["write_policy_denied"]
    assert summary["core_write_denied"]
