import json
import subprocess
import sys


def test_generic_ci_evidence_sample_completes_with_three_providers():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from agora_ai_sdlc.cli import main; sys.exit(main(['run-sample','ci-evidence']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["providers"] == ["github-actions", "gitlab-ci", "jenkins"]
    assert summary["categories"] == [
        "build",
        "deployment",
        "integration",
        "quality",
        "security",
        "smoke-test",
        "unit",
    ]
    assert summary["bundles"] == {"deployment": True, "security-scan": True, "test-suite": True}
    assert summary["observations"] == 7 and summary["idempotent_ingest"]
    assert "workspace" not in summary
