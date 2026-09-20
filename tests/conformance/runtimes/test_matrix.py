import json
from pathlib import Path

import pytest

from conformance.runtimes.harness import run_case

HERE = Path(__file__).parent
MATRIX = json.loads((HERE / "matrix.json").read_text())
SNAPSHOT = json.loads((HERE / "snapshot.json").read_text())
PROFILES = {"distinct-actor", "distinct-runtime", "distinct-provider", "human-final", "regulated"}


@pytest.mark.parametrize("case", MATRIX, ids=[case["id"] for case in MATRIX])
def test_offline_runtime_matrix_has_identical_lifecycle_semantics(case, tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    result = run_case(tmp_path / "project", case)
    assert result["snapshot"] == SNAPSHOT
    assert result["profiles"] == case["profiles"]
    assert result["data_allowed"] and result["selection_allowed"]
    assert result["session_runtimes"] == [
        [case["producer"]["runtime"][key] for key in ("integration", "provider", "model")],
        [case["reviewer"]["runtime"][key] for key in ("integration", "provider", "model")],
    ]


def test_every_review_profile_has_a_passing_and_failing_combination():
    assert {profile for case in MATRIX for profile in case["profiles"]} == PROFILES
    for profile in PROFILES:
        outcomes = {case["profiles"][profile] for case in MATRIX}
        assert outcomes == {False, True}
