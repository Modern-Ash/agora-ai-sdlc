from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc import verification
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.verification import build_verification_report


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


def test_run_executes_allowlisted_command_and_keeps_ac_unsatisfied(monkeypatch, tmp_path: Path):
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


def test_non_allowlisted_command_is_blocked_without_execution(monkeypatch, tmp_path: Path):
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
