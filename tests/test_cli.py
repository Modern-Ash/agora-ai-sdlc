import json

from agora_ai_sdlc import conformance
from agora_ai_sdlc.cli import main


def result(ok=True):
    return {
        "schema": "agora-ai-sdlc/self-test-result/v1",
        "ok": ok,
        "assets": {"methods": [], "profiles": [], "policies": [], "templates": [], "contracts": [], "samples": []},
        "role_conformance": {},
        "checks": [{"id": "assets", "kind": "inventory", "status": "passed" if ok else "failed"}],
        "failures": [] if ok else [{"check": "assets", "type": "ValueError", "message": "bad asset"}],
        "workspace": None if ok else "/tmp/retained-self-test",
    }


def test_self_test_json_keeps_stdout_machine_readable_and_progress_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr(conformance, "run_self_test", lambda progress: (progress("assets passed"), result())[1])
    assert main(["self-test", "--json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == result()
    assert captured.err == "[self-test] assets passed\n"


def test_self_test_failure_returns_nonzero_and_reports_workspace(monkeypatch, capsys):
    monkeypatch.setattr(conformance, "run_self_test", lambda progress: result(False))
    assert main(["self-test"]) == 1
    captured = capsys.readouterr()
    assert "self-test failed" in captured.out
    assert "Diagnostic workspace: /tmp/retained-self-test" in captured.out
