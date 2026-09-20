import json
import subprocess
import sys


def test_modernization_sample_blocks_failures_then_completes():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from agora_ai_sdlc.cli import main; raise SystemExit(main(['run-sample','modernization']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["slice_ids"] == ["checkout-total"]
    assert summary["known_behaviors"] == ["priced-cart"]
    assert summary["unknown_behaviors"] == ["empty-cart-rounding"]
    assert summary["blocked_paths"] == ["modernization.gate.blocked", "modernization.gate.blocked"]
    assert summary["accepted_difference"] == "empty-cart-rounding" and summary["rollback_validated"]
