import json
from pathlib import Path

import yaml

from agora_ai_sdlc import conformance
from agora_ai_sdlc.cli import main
from agora_ai_sdlc.compatibility_profiles import load_profile

ROOT = Path(__file__).parent.parent


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


def _write_conformance_facts(path, profile_id="aws-original", *, failed=False):
    from agora_ai_sdlc.compatibility_profiles import load_profile
    from agora_ai_sdlc.conformance.compatibility import FACTS_SCHEMA

    profile = load_profile(profile_id)
    facts = []
    for index, capability in enumerate(profile.required_capabilities):
        facts.append(
            {
                "capability": capability,
                "status": "FAIL" if failed and index == 0 else "PASS",
                "evidence": [f"repo://evidence/{capability}.md"],
                "reason": "missing control" if failed and index == 0 else "verified",
            }
        )
    path.write_text(yaml.safe_dump({"schema": FACTS_SCHEMA, "facts": facts}, sort_keys=False), encoding="utf-8")


def test_conformance_cli_json_and_human_output(tmp_path, capsys):
    facts = tmp_path / "facts.yaml"
    _write_conformance_facts(facts)

    assert main(["conformance", "aws-original", "--facts", str(facts), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"]["id"] == "aws-original"
    assert payload["overall_status"] == "PASS"
    assert payload["has_failures"] is False

    assert main(["conformance", "aws-original", "--facts", str(facts)]) == 0
    output = capsys.readouterr().out
    assert "Overall: PASS" in output
    assert f"contract: {load_profile('aws-original').version}" in output


def test_conformance_strict_mode_only_fails_valid_report_with_failures(tmp_path, capsys):
    facts = tmp_path / "facts.yaml"
    _write_conformance_facts(facts, failed=True)

    assert main(["conformance", "aws-original", "--facts", str(facts)]) == 0
    assert "Overall: FAIL" in capsys.readouterr().out

    assert main(["conformance", "aws-original", "--facts", str(facts), "--strict"]) == 1
    assert "Overall: FAIL" in capsys.readouterr().out


def test_conformance_bad_input_returns_two(tmp_path, capsys):
    missing = tmp_path / "missing.yaml"
    assert main(["conformance", "aws-original", "--facts", str(missing)]) == 2
    assert "conformance.fact_file" in capsys.readouterr().err

    assert main(["conformance", "missing-profile", "--root", str(tmp_path)]) == 2
    assert "conformance.profile" in capsys.readouterr().err


def test_conformance_derive_aws_original_uses_repository_rules(capsys):
    assert main(["conformance", "aws-original", "--derive", "--root", str(ROOT), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"]["id"] == "aws-original"
    assert payload["facts_source"] == "derived:aws-original-rules/v1"
    assert payload["overall_status"] == "PARTIAL"
    assert any(item["status"] == "PARTIAL" for item in payload["results"])
    assert any(item["status"] == "PASS" for item in payload["results"])
    assert not any(item["status"] == "FAIL" for item in payload["results"])


def test_conformance_derive_strict_and_provider_errors(tmp_path, capsys):
    assert main(["conformance", "aws-original", "--derive", "--root", str(ROOT), "--strict"]) == 0
    assert "Overall: PARTIAL" in capsys.readouterr().out

    facts = tmp_path / "facts.yaml"
    _write_conformance_facts(facts)
    assert main(["conformance", "aws-original", "--derive", "--facts", str(facts)]) == 2
    assert "mutually exclusive" in capsys.readouterr().err

    assert main(["conformance", "lg-enterprise", "--derive", "--root", str(ROOT)]) == 2
    assert "no derived fact provider" in capsys.readouterr().err


def test_plan_validate_cli_authorizes_valid_pathway(capsys):
    root = Path(__file__).parent.parent
    plan = root / "tests" / "fixtures" / "pathways" / "trivial-change.md"

    assert main(["plan-validate", str(plan), "--pathway", "trivial-change", "--depth", "standard", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["authorized"] is True
    assert payload["pathway"] == "trivial-change"
    assert payload["effective_depth"] == "standard"
    assert payload["lifecycle"] == ["inception", "construction", "operations"]


def test_plan_validate_cli_fails_closed_for_stricter_profile(capsys):
    root = Path(__file__).parent.parent
    plan = root / "tests" / "fixtures" / "pathways" / "trivial-change.md"

    assert main(["plan-validate", str(plan), "--pathway", "trivial-change", "--profile", "enterprise"]) == 2
    assert "pathway.mandatory_" in capsys.readouterr().err


def test_plan_validate_cli_rejects_unknown_pathway(capsys):
    root = Path(__file__).parent.parent
    plan = root / "tests" / "fixtures" / "pathways" / "trivial-change.md"

    assert main(["plan-validate", str(plan), "--pathway", "missing"]) == 2
    assert "pathway.unknown" in capsys.readouterr().err
