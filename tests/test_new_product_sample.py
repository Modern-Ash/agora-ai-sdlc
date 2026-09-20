import json
import subprocess
import sys

EXPECTED = [
    ("readiness", "intent"), ("intent", "inception"), ("inception", "construction"),
    ("construction", "inception"), ("inception", "construction"), ("construction", "operations"),
    ("operations", "completed"),
]  # fmt: skip


def test_sample_completes_with_expected_activity():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; from agora_ai_sdlc.cli import main; sys.exit(main(['run-sample','new-product']))"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert [(t["from"], t["to"]) for t in summary["transitions"]] == EXPECTED
    assert [b["reason"] for b in summary["blocked_gates"]] == [
        "Gate readiness-approved failed",
        "Gate rework-recorded failed",
    ]
    assert len(summary["rework_paths"]) == 1
    assert {
        "work.transitioned",
        "approval.added",
        "artifact.added",
        "evidence.added",
        "work.clarified-advisory",
    } <= set(summary["activity_actions"])
    assert "workspace" not in summary  # cleaned on success


def test_unknown_sample_fails():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; from agora_ai_sdlc.cli import main; sys.exit(main(['run-sample','../x']))"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 2
