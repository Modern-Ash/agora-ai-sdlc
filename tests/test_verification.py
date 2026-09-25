from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc import verification
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.verification import (
    build_verification_report,
    persisted_verification_diagnostic,
    persisted_verification_failed,
)


def bundle(tmp_path: Path, commands=("pnpm test",)) -> ExecutionBundle:
    return ExecutionBundle(
        schema="agora-ai-sdlc/execution-bundle/v1",
        swarm="delivery",
        work="issue-14",
        stage="construction",
        next_action="resolve-governance-obligations",
        branch="ai-sdlc/issue-14",
        base_branch="main",
        head="a" * 40,
        objective="Execute learner programs with an interpreter.",
        acceptance_criteria=("interpreter stop outcome explicit",),
        changed_paths=("src/interpreter.ts",),
        dirty_paths=(),
        related_paths=("src/interpreter.ts", "src/interpreter.spec.ts"),
        languages=("TypeScript",),
        build_systems=("pnpm",),
        verification_commands=tuple(commands),
        risks=(),
        governance={},
        deterministic_inception_path=str(tmp_path / "DETERMINISTIC_INCEPTION.md"),
        json_path=None,
        markdown_path=None,
    )


def test_plan_only_never_executes_commands(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(verification, "resolve_work_workspace", lambda root, work: tmp_path.resolve())
    monkeypatch.setattr(verification, "build_execution_bundle", lambda *args, **kwargs: bundle(tmp_path))

    def fail_run(*args, **kwargs):
        raise AssertionError("plan-only verification must not execute subprocesses")

    monkeypatch.setattr(verification.subprocess, "run", fail_run)

    report = build_verification_report(tmp_path, work="issue-14", run=False, persist=False)

    assert report.executed is False
    assert report.commands[0].status == "planned"
    assert report.all_executed_commands_passed is None
    assert report.acceptance_coverage[0].candidate_test_paths == ("src/interpreter.spec.ts",)
    assert report.acceptance_coverage[0].mechanically_satisfied is False


def test_run_resolves_work_workspace_before_execution(monkeypatch, tmp_path: Path):
    primary = tmp_path / "primary"
    worktree = tmp_path / "issue-14"
    primary.mkdir()
    worktree.mkdir()

    monkeypatch.setattr(
        verification,
        "resolve_work_workspace",
        lambda root, work: worktree.resolve(),
    )
    monkeypatch.setattr(
        verification,
        "build_execution_bundle",
        lambda root, **kwargs: bundle(worktree),
    )
    observed = {}

    def fake_run(argv, **kwargs):
        observed["cwd"] = kwargs["cwd"]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(verification.subprocess, "run", fake_run)

    report = build_verification_report(primary, work="issue-14", run=True, persist=False)

    assert observed["cwd"] == worktree.resolve()
    assert report.commands[0].status == "passed"


def test_run_executes_allowlisted_command_and_keeps_ac_unsatisfied(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(verification, "resolve_work_workspace", lambda root, work: tmp_path.resolve())
    monkeypatch.setattr(verification, "build_execution_bundle", lambda *args, **kwargs: bundle(tmp_path))
    observed = {}

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="3 tests passed", stderr="")

    monkeypatch.setattr(verification.subprocess, "run", fake_run)

    report = build_verification_report(tmp_path, work="issue-14", run=True, persist=False)

    assert observed["argv"] == ["pnpm", "test"]
    assert observed["cwd"] == tmp_path.resolve()
    assert observed["timeout"] == 300
    assert report.commands[0].status == "passed"
    assert report.all_executed_commands_passed is True
    assert report.acceptance_coverage[0].mechanically_satisfied is False


def test_failed_command_renders_compact_diagnostic(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        verification,
        "resolve_work_workspace",
        lambda root, work: tmp_path.resolve(),
    )
    monkeypatch.setattr(verification, "build_execution_bundle", lambda *args, **kwargs: bundle(tmp_path))

    def fake_run(argv, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL interpreter tests failed",
        )

    monkeypatch.setattr(verification.subprocess, "run", fake_run)

    report = build_verification_report(tmp_path, work="issue-14", run=True, persist=False)
    rendered = verification.render_verification(report)

    assert "[failed] pnpm test" in rendered
    assert "exit=1" in rendered
    assert "diagnostic: ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL interpreter tests failed" in rendered


def test_non_allowlisted_command_is_blocked_without_execution(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(verification, "resolve_work_workspace", lambda root, work: tmp_path.resolve())
    monkeypatch.setattr(
        verification,
        "build_execution_bundle",
        lambda *args, **kwargs: bundle(tmp_path, commands=("rm -rf .",)),
    )

    def fail_run(*args, **kwargs):
        raise AssertionError("blocked command must not execute")

    monkeypatch.setattr(verification.subprocess, "run", fail_run)

    report = build_verification_report(tmp_path, work="issue-14", run=True, persist=False)

    assert report.commands[0].allowed is False
    assert report.commands[0].status == "blocked"
    assert report.all_executed_commands_passed is False


def test_persisted_report_remains_renderable_with_typed_commands(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(verification, "build_execution_bundle", lambda *args, **kwargs: bundle(tmp_path))

    report = build_verification_report(tmp_path, work="issue-14", run=False, persist=True)
    rendered = verification.render_verification(report)

    assert report.commands[0].status == "planned"
    assert report.acceptance_coverage[0].criterion == "interpreter stop outcome explicit"
    assert "[planned] pnpm test" in rendered


def test_report_is_persisted_as_durable_bounded_json(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(verification, "build_execution_bundle", lambda *args, **kwargs: bundle(tmp_path))

    report = build_verification_report(tmp_path, work="issue-14", run=False, persist=True)

    assert report.report_path is not None
    path = Path(report.report_path)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "agora-ai-sdlc/verification-report/v1" in text
    assert "mechanically_satisfied" in text


def test_java_maven_build_is_run_before_tests(monkeypatch, tmp_path: Path):
    java_bundle = bundle(tmp_path, commands=("mvn test",))
    java_bundle = ExecutionBundle(
        **{
            **java_bundle.__dict__,
            "build_systems": ("Maven",),
        }
    )
    (tmp_path / "mvnw").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(verification, "resolve_work_workspace", lambda root, work: tmp_path.resolve())
    monkeypatch.setattr(verification, "build_execution_bundle", lambda *args, **kwargs: java_bundle)

    commands = []

    def fake_run(argv, **kwargs):
        commands.append(tuple(argv))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(verification.subprocess, "run", fake_run)

    report = build_verification_report(tmp_path, work="issue-14", run=True, persist=False)

    assert commands == [
        ("./mvnw", "-q", "-DskipTests", "package"),
        ("mvn", "test"),
    ]
    assert report.all_executed_commands_passed is True


def test_persisted_verification_failed_detects_failed_or_unrunnable_execution(tmp_path: Path):
    target = tmp_path / ".agora" / "ai-sdlc" / "verification" / "issue-14" / "VERIFICATION.json"
    target.parent.mkdir(parents=True)

    target.write_text(
        '{"executed": true, "commands": [{"status": "failed"}]}\n',
        encoding="utf-8",
    )
    assert persisted_verification_failed(tmp_path, "issue-14") is True

    target.write_text(
        '{"executed": true, "commands": []}\n',
        encoding="utf-8",
    )
    assert persisted_verification_failed(tmp_path, "issue-14") is True


def test_persisted_verification_failed_is_false_after_success(tmp_path: Path):
    target = tmp_path / ".agora" / "ai-sdlc" / "verification" / "issue-14" / "VERIFICATION.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        '{"executed": true, "commands": [{"status": "passed"}, {"status": "passed"}]}\n',
        encoding="utf-8",
    )

    assert persisted_verification_failed(tmp_path, "issue-14") is False


def test_persisted_verification_diagnostic_reports_missing_commands(tmp_path: Path):
    target = tmp_path / ".agora" / "ai-sdlc" / "verification" / "issue-14" / "VERIFICATION.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"executed": true, "commands": []}\n', encoding="utf-8")

    diagnostic = persisted_verification_diagnostic(tmp_path, "issue-14")

    assert diagnostic is not None
    assert "No deterministic build/test command was detected" in diagnostic


def test_persisted_verification_diagnostic_compacts_failed_command(tmp_path: Path):
    target = tmp_path / ".agora" / "ai-sdlc" / "verification" / "issue-14" / "VERIFICATION.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "executed": True,
                "commands": [
                    {
                        "command": "npm test",
                        "status": "failed",
                        "exit_code": 1,
                        "stderr": "AssertionError: expected 90 but got 100",
                        "stdout": "",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    diagnostic = persisted_verification_diagnostic(tmp_path, "issue-14")

    assert diagnostic == "npm test: failed exit=1 diagnostic=AssertionError: expected 90 but got 100"
