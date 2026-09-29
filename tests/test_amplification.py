import json

import pytest

from agora_ai_sdlc.amplification import (
    TokenMeasurement,
    amplification_report,
    save_baseline,
)


def test_amplification_uses_only_explicit_provider_reported_baseline(tmp_path):
    save_baseline(tmp_path, "issue-1", TokenMeasurement(800, 200))

    report = amplification_report(tmp_path, "issue-1", TokenMeasurement(600, 150))

    assert report.comparable is True
    assert report.factor == 0.75
    assert report.reason == "measured"


def test_amplification_is_unknown_without_baseline(tmp_path):
    report = amplification_report(tmp_path, "issue-2", TokenMeasurement(600, 150))

    assert report.comparable is False
    assert report.factor is None
    assert report.reason == "baseline-missing"


def test_amplification_is_unknown_without_agora_usage(tmp_path):
    save_baseline(tmp_path, "issue-3", TokenMeasurement(800, 200))

    report = amplification_report(tmp_path, "issue-3", None)

    assert report.comparable is False
    assert report.factor is None
    assert report.reason == "agora-usage-missing"


def test_non_provider_token_basis_is_rejected():
    with pytest.raises(ValueError, match="provider-reported"):
        TokenMeasurement(100, 10, basis="estimated_tokens")


def test_invalid_persisted_baseline_fails_closed(tmp_path):
    path = tmp_path / ".agora" / "ai-sdlc" / "economics" / "issue-4" / "BASELINE.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema": "wrong", "measurement": {}}), encoding="utf-8")

    report = amplification_report(tmp_path, "issue-4", TokenMeasurement(1, 1))

    assert report.factor is None
    assert report.reason == "baseline-missing"
