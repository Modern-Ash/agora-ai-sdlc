import json
import shlex
import sys

import pytest
from agora.model import StartSessionInput
from conformance.runtimes.harness import _workspace, normalize_output

from agora_ai_sdlc.ci_evidence import normalize_evidence
from agora_ai_sdlc.runtime_selection import Candidate, Route, RuntimeRef, select_runtime

ALLOW = {"allowed": True, "blockers": []}
COMMIT = "a" * 40


def _route():
    return Route(
        "implementation",
        (
            Candidate(RuntimeRef("primary", "generic", "provider-a", "model-a"), {}, ALLOW, ALLOW),
            Candidate(RuntimeRef("secondary", "generic", "provider-b", "model-b"), {}, ALLOW, ALLOW),
        ),
    )


def _session_workspace(tmp_path, monkeypatch, name):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / f"{name}-home"))
    return _workspace(tmp_path / name, "ai-agent", False)


def _ordinary_failure_blocks_fallback():
    decision = select_runtime(_route(), signal="ordinary-failure", current_runtime="primary")
    assert not decision["allowed"] and decision["selected"] is None
    assert decision["blockers"][0]["code"] == "fallback.ordinary_failure"


def test_malformed_provider_output_is_distinct_and_never_selects_fallback(tmp_path, monkeypatch):
    workspace = _session_workspace(tmp_path, monkeypatch, "malformed")
    raw = "not-json"
    runner = shlex.join([sys.executable, "-c", f"print({raw!r})"])
    session = workspace.start_session(
        StartSessionInput("producer", "delivery", "malformed-output", "increment", runner, True)
    )

    assert session.status == "completed" and session.termination_reason is None
    with pytest.raises(json.JSONDecodeError):
        normalize_output("generic", raw)
    _ordinary_failure_blocks_fallback()


def test_real_core_timeout_is_durable_and_never_selects_fallback(tmp_path, monkeypatch):
    workspace = _session_workspace(tmp_path, monkeypatch, "timeout")
    runner = shlex.join([sys.executable, "-c", "import time; time.sleep(5)"])
    with pytest.raises(RuntimeError, match=r"\(timeout\)"):
        workspace.start_session(
            StartSessionInput(
                "producer",
                "delivery",
                "timed-out",
                "increment",
                runner,
                True,
                timeout_seconds=1,
            )
        )

    session = workspace.show_session("timed-out")
    assert session.status == "failed" and session.exit_code == 124
    assert session.termination_reason == "timeout"
    _ordinary_failure_blocks_fallback()


def test_quota_is_an_explicit_distinct_authorized_fallback_signal():
    decision = select_runtime(_route(), signal="quota", current_runtime="primary")
    assert decision["allowed"] and decision["selected"]["id"] == "secondary"
    assert decision["fallback"] == {"used": True, "reason": "quota"}


def test_cancelled_ci_run_is_distinct_and_never_selects_runtime_fallback():
    fact = normalize_evidence(
        {
            "schema": "agora-ai-sdlc/ci-evidence/v1",
            "provider": "generic-ci",
            "repository": "https://example.test/project",
            "commit": COMMIT,
            "environment": "ci",
            "run_id": "cancelled-40",
            "category": "build",
            "status": "cancelled",
            "evidence_refs": ["https://example.test/run/cancelled-40"],
        },
        expected_repository="https://example.test/project",
        expected_commit=COMMIT,
        expected_environment="ci",
    )
    assert not fact["allowed"]
    assert {blocker["code"] for blocker in fact["blockers"]} == {"ci.status.cancelled"}
    _ordinary_failure_blocks_fallback()


def test_unavailable_runner_fails_before_session_write_and_can_use_explicit_fallback(tmp_path, monkeypatch):
    workspace = _session_workspace(tmp_path, monkeypatch, "unavailable")
    with pytest.raises(FileNotFoundError, match="Runtime executable not found"):
        workspace.start_session(
            StartSessionInput(
                "producer",
                "delivery",
                "runner-unavailable",
                "increment",
                "agora-runner-that-does-not-exist-40",
                True,
            )
        )
    assert not (tmp_path / "unavailable" / ".agora" / "sessions" / "runner-unavailable").exists()

    decision = select_runtime(_route(), signal="runtime-unavailable", current_runtime="primary")
    assert decision["allowed"] and decision["selected"]["id"] == "secondary"
    assert decision["fallback"] == {"used": True, "reason": "runtime-unavailable"}
