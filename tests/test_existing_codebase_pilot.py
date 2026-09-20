import json
import subprocess
import sys


def test_existing_codebase_pilot_rejects_corrects_and_completes():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from agora_ai_sdlc.cli import main; raise SystemExit(main(['run-sample','existing-codebase-pilot']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["provider_replacement"] == {
        "before": "provider-alpha",
        "after": "provider-beta",
        "method_pack_unchanged": True,
    }
    assert [review["verdict"] for review in summary["reviews"]] == ["changes-requested", "approved"]
    assert [review["allowed"] for review in summary["reviews"]] == [False, True]
    assert summary["reviews"][0]["blockers"] == ["review.verdict"]
    for review in summary["reviews"]:
        assert review["producer"]["actor"] != review["reviewer"]["actor"]
        assert review["producer"]["provider"] != review["reviewer"]["provider"]
    assert summary["blocked_gate"] == "Gate build-verified failed"
    assert summary["ci"]["allowed"] and summary["ci"]["commit"] == summary["commits"]["accepted"]
    assert summary["ci"]["categories"] == ["build", "unit", "integration", "quality"]
    assert summary["metrics"]["measured"] == {
        "baseline_tests": 3,
        "baseline_passing": True,
        "first_revision_tests": 4,
        "result_tests": 5,
        "result_passing": True,
        "review_rounds": 2,
        "gate_rejections": 1,
    }
    assert len(summary["metrics"]["expectations_not_measured"]) == 3
    assert "workspace" not in summary
