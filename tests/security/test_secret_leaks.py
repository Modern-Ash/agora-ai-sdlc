import json
import socket

import pytest

from agora_ai_sdlc.ci_evidence import CIEvidenceError, normalize_evidence
from agora_ai_sdlc.conformance import run_self_test
from agora_ai_sdlc.conformance import self_test as harness
from agora_ai_sdlc.provenance import ProvenanceError, parse

CANARY = "agora-canary-secret-40-do-not-persist"
COMMIT = "a" * 40


def _deny_network(*_args, **_kwargs):
    raise AssertionError("offline conformance attempted a network connection")


def test_all_samples_and_validation_are_offline_and_do_not_persist_environment_canary(monkeypatch, tmp_path):
    workspace = tmp_path / "self-test"
    workspace.mkdir()
    real_rmtree = harness.shutil.rmtree

    def create_workspace(*_args, **_kwargs):
        return str(workspace)

    def preserve_workspace(path, *args, **kwargs):
        if path == workspace or str(path) == str(workspace):
            return None
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(harness, "mkdtemp", create_workspace)
    monkeypatch.setattr(harness.shutil, "rmtree", preserve_workspace)
    monkeypatch.setattr(socket.socket, "connect", _deny_network)
    monkeypatch.setattr(socket, "create_connection", _deny_network)
    monkeypatch.setenv("AGORA_TEST_CANARY", CANARY)
    progress = []

    result = run_self_test(progress=progress.append)

    assert result["ok"] and len(result["assets"]["samples"]) == 11
    observed = [json.dumps(result, sort_keys=True), *progress]
    observed.extend(
        path.read_bytes().decode("utf-8", errors="replace") for path in workspace.rglob("*") if path.is_file()
    )
    assert all(CANARY not in value for value in observed)


def test_secret_bearing_inputs_are_rejected_without_echoing_canary():
    provenance = {
        "schema": "agora-ai-sdlc/provenance/v1",
        "actor": "builder",
        "runtime": {"value": "generic", "source": "observed"},
        "runtime_version": {"value": "1", "source": "observed"},
        "provider": {"value": "local", "source": "observed"},
        "model": {"value": "model", "source": "observed"},
        "selection_reason": {"value": "policy", "source": "observed"},
        "fallback": {"source": "observed", "used": False},
        "api_key": CANARY,
    }
    with pytest.raises(ProvenanceError) as provenance_error:
        parse(provenance)
    assert provenance_error.value.code in {"provenance.secret", "provenance.unknown_field"}
    assert CANARY not in str(provenance_error.value)

    ci_payload = {
        "schema": "agora-ai-sdlc/ci-evidence/v1",
        "provider": "generic-ci",
        "repository": "https://example.test/project",
        "commit": COMMIT,
        "environment": "ci",
        "run_id": "run-40",
        "category": "build",
        "status": "success",
        "evidence_refs": [f"https://example.test/run/40?token={CANARY}"],
    }
    with pytest.raises(CIEvidenceError) as ci_error:
        normalize_evidence(
            ci_payload,
            expected_repository="https://example.test/project",
            expected_commit=COMMIT,
            expected_environment="ci",
        )
    assert ci_error.value.code == "ci.fact.reference"
    assert CANARY not in str(ci_error.value)
