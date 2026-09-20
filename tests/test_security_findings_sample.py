import json
import subprocess
import sys


def test_security_findings_sample_blocks_then_completes_with_accountable_decisions():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from agora_ai_sdlc.cli import main; sys.exit(main(['run-sample','security-findings']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["categories"] == ["container", "dependency", "iac", "sast", "secret"]
    assert summary["blocked_before_decisions"] and summary["allowed_after_decisions"]
    assert summary["decisions"] == ["accepted-risk", "false-positive", "resolved"]
    assert summary["open_below_threshold"] == ["container-hardening-004", "iac-tag-005"]
    assert summary["core_statuses"] == ["open", "open", "resolved", "waived", "waived"]
    assert "workspace" not in summary
