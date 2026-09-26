from types import SimpleNamespace

import pytest
from support.lifecycle import Lifecycle

from agora_ai_sdlc.governance_guard import GovernanceRegression, guard_governed_state


def issue(code, path, severity="error"):
    return SimpleNamespace(code=code, path=path, message=f"{code} msg", severity=severity)


def factory_with(*reports):
    reports = list(reports)

    def factory(cwd):
        current = reports.pop(0)
        if isinstance(current, Exception):
            raise current
        return SimpleNamespace(validate=lambda: SimpleNamespace(issues=current))

    return factory


def test_new_error_introduced_by_run_blocks(tmp_path):
    factory = factory_with([], [issue("intent.invalid", ".agora/intents/i/INTENT.md")])
    with pytest.raises(GovernanceRegression) as error, guard_governed_state(tmp_path, workspace_factory=factory):
        pass
    assert error.value.issues[0][:2] == ("intent.invalid", ".agora/intents/i/INTENT.md")
    assert "nothing was approved" in str(error.value)


def test_preexisting_errors_and_warnings_never_block(tmp_path):
    old = issue("clarifications.stale", "a")
    factory = factory_with([old], [old, issue("style.nit", "b", "warning")])
    with guard_governed_state(tmp_path, workspace_factory=factory):
        pass


def test_unavailable_baseline_skips_and_unavailable_after_fails_closed(tmp_path):
    with guard_governed_state(tmp_path, workspace_factory=factory_with(ValueError("broken"))):
        pass
    with (
        pytest.raises(GovernanceRegression) as error,
        guard_governed_state(tmp_path, workspace_factory=factory_with([], OSError("gone"))),
    ):
        pass
    assert error.value.code == "governance.validation_unavailable"


def test_body_exception_propagates_without_masking(tmp_path):
    with (
        pytest.raises(RuntimeError, match="executor died"),
        guard_governed_state(tmp_path, workspace_factory=factory_with([])),
    ):
        raise RuntimeError("executor died")


def test_real_workspace_detects_overwritten_intent(tmp_path, monkeypatch):
    project = Lifecycle(tmp_path / "project", tmp_path / "home", monkeypatch).root
    intent = project / ".agora" / "intents" / "issue-1"
    intent.mkdir(parents=True)
    with pytest.raises(GovernanceRegression) as error, guard_governed_state(project):
        (intent / "INTENT.md").write_text("# Intent\n", encoding="utf-8")
    assert [code for code, _, _ in error.value.issues] == ["intent.invalid"]
    with guard_governed_state(project):  # already broken before the run: not this run's fault
        pass
