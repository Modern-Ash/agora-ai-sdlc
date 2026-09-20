import json
import subprocess
import sys


def test_enterprise_sample_installs_and_upgrades_signed_snapshot():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from agora_ai_sdlc.cli import main; raise SystemExit(main(['run-sample','enterprise']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["install_preview_matches"] and summary["upgrade_previewed"] and summary["upgrade_applied"]
    assert summary["signature_verified"] and summary["provenance_recorded"]
    assert summary["rollback_strategy"] == "signed-forward-release"
