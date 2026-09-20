import json
import subprocess
import sys


def test_operational_evidence_sample_completes_and_proposes_governed_intent():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from agora_ai_sdlc.cli import main; sys.exit(main(['run-sample','operational-evidence']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["providers"] == [
        "azure-monitor",
        "cloudwatch",
        "gcp-monitoring",
        "opentelemetry",
        "prometheus",
    ]
    assert summary["equivalent_metrics"] and summary["readiness_allowed"]
    assert summary["control_band_level"] == "propose" and summary["governed_intent"]
    assert summary["production_mutations"] == 0 and "workspace" not in summary
