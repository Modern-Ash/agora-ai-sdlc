import json
import re
import subprocess
import sys
from pathlib import Path

REPORT = (Path(__file__).parent.parent / "docs" / "pilots" / "modernization.md").read_text(encoding="utf-8")


def run_sample() -> dict:
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
    return json.loads(result.stdout)


def test_pilot_report_matches_the_sample_it_describes():
    summary = run_sample()
    for label, value in (
        ("Final lifecycle state", summary["final_state"]),
        ("Accepted difference", summary["accepted_difference"]),
        ("`agora validate`", summary["validate"]),
    ):
        assert re.search(rf"\| {re.escape(label)} \| `?{re.escape(value)}`? \|", REPORT), label
    assert f"| Gate blocks before completion | {len(summary['blocked_paths'])} " in REPORT
    assert f"| Slice | `{summary['slice_ids'][0]}`" in REPORT
    assert f"`{summary['known_behaviors'][0]}`" in REPORT and f"`{summary['unknown_behaviors'][0]}`" in REPORT
    assert summary["rollback_validated"] and "| Rollback validated | yes |" in REPORT


def test_pilot_report_states_baseline_outcome_evidence_and_limitations():
    for heading in ("## Baseline", "## Outcome", "## Evidence", "## Limitations", "## Optional live pilot"):
        assert heading in REPORT
    lowered = REPORT.lower()
    assert "not measured and are not claimed" in lowered
    assert "not a compliance or migration-success guarantee" in lowered
