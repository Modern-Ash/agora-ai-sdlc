import json
import subprocess
import sys


def test_regulated_sample_completes_a_fully_signed_lifecycle_and_shows_rejections():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from agora_ai_sdlc.cli import main; raise SystemExit(main(['run-sample','regulated']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["final_state"] == "completed" and summary["validate"] == "ok"
    assert summary["signed_actions"] >= 30
    assert summary["rejected"] == {
        "unsigned_mutation": "signed-lifecycle-action-required",
        "non_human_product_owner": "regulated.assignment.human",
        "builder_reviewer_combination": "regulated.assignment.segregation",
        "unauthorized_exception": "regulated.exception.authority",
        "non_waivable_exception": "regulated.exception.policy",
    }
    assert summary["provenance_gate"] == {"declared": False, "observed": True}
    assert summary["exception_recorded"] and summary["retention_records"] == 3


def test_regulated_sample_leaves_no_key_material_in_its_summary():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from agora_ai_sdlc.cli import main; raise SystemExit(main(['run-sample','regulated']))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "PRIVATE KEY" not in result.stdout + result.stderr
