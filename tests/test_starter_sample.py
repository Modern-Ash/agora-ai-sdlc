import json
import subprocess
import sys


def test_starter_sample_bootstraps_first_work():
    result = subprocess.run(
        [sys.executable, "-c", "from agora_ai_sdlc.cli import main; raise SystemExit(main(['run-sample','starter']))"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["preview_matches"] and summary["first_work_state"] == "readiness"
    assert summary["method"] == {"id": "ai-sdlc", "version": "0.1.0"}
