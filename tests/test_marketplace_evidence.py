from pathlib import Path

import pytest

from agora_ai_sdlc import marketplace_evidence

ROOT = Path(__file__).parent.parent


def test_generated_marketplace_matrix_is_deterministic_and_current():
    first = marketplace_evidence.generate(ROOT)
    second = marketplace_evidence.generate(ROOT)

    assert first == second
    assert (ROOT / marketplace_evidence.GENERATED_RELATIVE).read_text(encoding="utf-8") == first
    assert "| Evidence dimension | AWS-original | LG-enterprise | Agora-open |" in first
    assert "risk-issue-management" in first
    assert "recursive-planning" in first
    assert "additive governance only" in first


def test_matrix_preserves_lg_public_boundary_and_aws_gaps():
    rendered = marketplace_evidence.generate(ROOT)

    assert "LG-enterprise statuses come from the repository-derived public-profile provider" in rendered
    assert "no proprietary LG behavior is inferred" in rendered
    assert "PARTIAL/FAIL remain visible" in rendered
    assert "Agora-specific governance is never counted as AWS-original fidelity" in rendered


@pytest.mark.parametrize("phrase", marketplace_evidence.FORBIDDEN_IMPLICATIONS)
def test_generated_matrix_never_contains_forbidden_endorsement_implications(phrase):
    assert phrase not in marketplace_evidence.generate(ROOT).casefold()


def test_check_fails_when_generated_file_is_missing_or_stale(tmp_path, monkeypatch):
    relative = marketplace_evidence.GENERATED_RELATIVE
    monkeypatch.setattr(marketplace_evidence, "generate", lambda _root: "expected\n")

    ok, message = marketplace_evidence.check(tmp_path)
    assert not ok
    assert "missing generated evidence matrix" in message

    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text("stale\n", encoding="utf-8")

    ok, message = marketplace_evidence.check(tmp_path)
    assert not ok
    assert "stale" in message

    target.write_text("expected\n", encoding="utf-8")
    assert marketplace_evidence.check(tmp_path) == (True, "compatibility evidence matrix is current")
