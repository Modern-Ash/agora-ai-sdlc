import json
import subprocess
import sys


def test_github_delivery_sample_is_offline_read_only_and_complete():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from agora_ai_sdlc.cli import main; sys.exit(main(['run-sample','github-delivery']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["profile_mode"] == "read-only"
    assert summary["delivery_allowed"] and summary["idempotent_ingest"]
    assert summary["write_policy_denied"] and summary["core_write_denied"]
    assert summary["prepared_operations"] == [
        "github-issues/view",
        "github-pull-requests/view",
        "github-actions/view-run",
    ]
    assert all(reference.startswith("https://github.com/") for reference in summary["evidence_references"])
    assert "workspace" not in summary
