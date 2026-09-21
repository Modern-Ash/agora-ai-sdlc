import runpy
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_adaptive_delivery_sample_composes_epic_92_capabilities():
    module = runpy.run_path(str(ROOT / "samples" / "adaptive-delivery" / "run.py"), run_name="adaptive_delivery_test")
    summary = module["main"]()

    assert summary["method_version"] == "0.2.0"
    assert summary["final_state"] == "completed"
    assert summary["recursive_plan"] == {
        "level1": "PLN-001",
        "level2": "PLN-002",
        "parent": "PLN-001",
        "approved": True,
    }
    assert summary["parallel_ready_bolts"] == ["api", "ui"]
    assert summary["construction_evidence_complete"] is True
    assert summary["unrelated_excluded"] is True
    assert summary["validate"] == "ok"
