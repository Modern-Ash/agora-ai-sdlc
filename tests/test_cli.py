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

    assert main(["conformance", "lg-enterprise", "--derive", "--root", str(ROOT), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"]["id"] == "lg-enterprise"
    assert payload["facts_source"] == "derived:lg-enterprise-rules/v1"
    assert payload["overall_status"] == "PASS"
    assert any(
        item["capability"] == "risk-issue-management" and item["status"] == "PASS" for item in payload["results"]
    )


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


def test_bolt_validate_cli_reports_trace_and_fails_closed(capsys, tmp_path):
    root = Path(__file__).parent.parent
    fixture = root / "tests" / "fixtures" / "bolts" / "parallel.md"

    assert main(["bolt-validate", str(fixture), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unit"] == "UOW-001"
    assert payload["ready"] == ["ui"]

    broken = tmp_path / "conflict.md"
    broken.write_text(fixture.read_text(encoding="utf-8").replace('writes: ["src/ui/"]', 'writes: ["src/api/"]'))
    assert main(["bolt-validate", str(broken)]) == 2
    assert "bolt.parallel_conflict" in capsys.readouterr().err


def _guided_decision():
    from agora_ai_sdlc.guided import GuidedDecision

    return GuidedDecision(
        swarm="delivery",
        work="first-work",
        title="Deliver first governed outcome",
        method="ai-sdlc",
        actor="project:product-owner",
        role="product-owner",
        state="readiness",
        target="intent",
        gate="readiness-approved",
        blockers=("Gate readiness-approved failed: missing-artifacts=[readiness-assessment]",),
        messages=("Prepare the required project evidence: readiness-assessment.",),
        missing_artifacts=("readiness-assessment",),
    )


def test_guided_continue_cli_hides_core_blockers_by_default(monkeypatch, capsys):
    decision = _guided_decision()
    monkeypatch.setattr("agora_ai_sdlc.guided.inspect_next", lambda *args, **kwargs: decision)

    assert main(["continue"]) == 0
    output = capsys.readouterr().out
    assert "Objective: Deliver first governed outcome" in output
    assert "Prepare the required project evidence" in output
    assert "missing-artifacts" not in output

    assert main(["continue", "--expert"]) == 0
    expert = capsys.readouterr().out
    assert "missing-artifacts=[readiness-assessment]" in expert
    assert "Structured decision" in expert


def test_guided_continue_cli_can_show_commands_and_json(monkeypatch, capsys):
    decision = _guided_decision()
    monkeypatch.setattr("agora_ai_sdlc.guided.inspect_next", lambda *args, **kwargs: decision)

    assert main(["continue", "--commands"]) == 0
    commands = capsys.readouterr().out
    assert "Underlying command bundle" in commands
    assert "agora artifact add" in commands

    assert main(["continue", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gate"] == "readiness-approved"
    assert payload["missing_artifacts"] == ["readiness-assessment"]


def test_runtimes_cli_human_and_json(monkeypatch, capsys):
    from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery

    discovered = (
        RuntimeDiscovery(
            id="codex",
            name="Codex",
            command="codex",
            installed=True,
            executable="/bin/codex",
            responsive=True,
            version="codex 1.0",
            configured=True,
        ),
    )
    monkeypatch.setattr("agora_ai_sdlc.runtime_discovery.discover_runtimes", lambda *args, **kwargs: discovered)
    monkeypatch.setattr("agora_ai_sdlc.runtime_discovery.render_runtimes", lambda items: "runtime-report")

    assert main(["runtimes"]) == 0
    assert capsys.readouterr().out.strip() == "runtime-report"

    assert main(["runtimes", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["id"] == "codex"
    assert payload[0]["configured"] is True


def test_doctor_cli_human_and_json(monkeypatch, capsys):
    from agora_ai_sdlc.doctor import DoctorCheck
    from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery

    checks = (DoctorCheck("project", True, "valid Agora project"),)
    runtimes = (
        RuntimeDiscovery(
            id="ollama",
            name="Ollama",
            command="ollama",
            installed=True,
            executable="/bin/ollama",
            responsive=True,
            version="ollama 1.0",
            configured=False,
            service="responsive",
        ),
    )
    monkeypatch.setattr("agora_ai_sdlc.doctor.run_doctor", lambda root: (checks, runtimes))
    monkeypatch.setattr("agora_ai_sdlc.doctor.render_doctor", lambda c, r: "doctor-report")

    assert main(["doctor"]) == 0
    assert capsys.readouterr().out.strip() == "doctor-report"

    assert main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"][0]["id"] == "project"
    assert payload["runtimes"][0]["service"] == "responsive"


def test_continue_uses_interactive_loop_on_tty(monkeypatch):
    called = {}

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.run_interactive",
        lambda root, swarm=None, work=None: called.update(root=str(root), swarm=swarm, work=work),
    )

    assert main(["continue", "--swarm", "delivery", "--work", "first-work"]) == 0
    assert called == {"root": ".", "swarm": "delivery", "work": "first-work"}


def test_continue_non_interactive_flag_skips_session(monkeypatch, capsys):
    decision = _guided_decision()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("agora_ai_sdlc.guided.inspect_next", lambda *args, **kwargs: decision)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("interactive loop must not run")

    monkeypatch.setattr("agora_ai_sdlc.guided_session.run_interactive", fail_if_called)

    assert main(["continue", "--non-interactive"]) == 0
    output = capsys.readouterr().out
    assert "Objective: Deliver first governed outcome" in output


def test_continue_json_stays_non_interactive_on_tty(monkeypatch, capsys):
    decision = _guided_decision()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("agora_ai_sdlc.guided.inspect_next", lambda *args, **kwargs: decision)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("interactive loop must not run")

    monkeypatch.setattr("agora_ai_sdlc.guided_session.run_interactive", fail_if_called)

    assert main(["continue", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["work"] == "first-work"


def test_start_interrupt_returns_130_without_traceback(monkeypatch, capsys, tmp_path):
    from agora_ai_sdlc import start_flow

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(start_flow, "prepare_start", interrupt)

    assert main(["start", "--issue", "14", "--root", str(tmp_path)]) == 130
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Start cancelled by user.\n"


def test_start_recoverable_failure_prompts_and_retries_selected_model(monkeypatch, capsys, tmp_path):
    from agora_ai_sdlc.executor_recovery import ExecutorRecoveryChoice
    from agora_ai_sdlc.start_flow import StartExecutorError

    calls = []

    def prepare(root, **kwargs):
        calls.append((kwargs.get("agent"), kwargs.get("model")))
        if len(calls) == 1:
            raise StartExecutorError(
                "Inception executor OpenCode failed: usage limit reached",
                runtime_id="opencode",
                workspace_root=str(tmp_path),
                recoverable=True,
            )
        return object()

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    monkeypatch.setattr("agora_ai_sdlc.start_flow.prepare_start", prepare)
    monkeypatch.setattr(
        "agora_ai_sdlc.start_flow.render_start",
        lambda result, **kwargs: "recovered",
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.executor_recovery.prompt_executor_recovery",
        lambda *args, **kwargs: ExecutorRecoveryChoice(
            agent="opencode",
            model="ollama/claude",
            label="OpenCode · ollama/claude [local]",
        ),
    )

    assert (
        main(
            [
                "start",
                "--issue",
                "14",
                "--agent",
                "opencode",
                "--root",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert calls == [
        ("opencode", None),
        ("opencode", "ollama/claude"),
    ]
    assert "recovered" in capsys.readouterr().out


def test_start_rejects_model_with_non_opencode_agent(capsys):
    assert main(["start", "--issue", "14", "--agent", "claude", "--model", "claude-sonnet"]) == 2
    assert "--model can only be used with --agent opencode" in capsys.readouterr().err
