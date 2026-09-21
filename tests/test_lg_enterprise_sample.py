import runpy
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_lg_enterprise_sample_composes_public_profile_capabilities():
    module = runpy.run_path(str(ROOT / "samples" / "lg-enterprise" / "run.py"), run_name="lg_enterprise_test")
    summary = module["main"]()

    assert summary["final_state"] == "completed"
    assert summary["validate"] == "ok"
    assert summary["profile"] == "lg-enterprise"
    assert summary["conformance"] == "PASS"
    assert summary["risk_issue_management"] == "PASS"
    assert summary["enterprise_reviews_allowed"] is True
    assert summary["enterprise_controls_allowed"] is True
    assert all(summary["exercised"].values())
    assert [stage["id"] for stage in summary["presentation"]["stages"]] == [
        "initialization",
        "ideation",
        "inception",
        "construction",
        "operation",
    ]
