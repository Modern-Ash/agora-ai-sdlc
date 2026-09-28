from pathlib import Path

from agora_ai_sdlc.doctor import run_doctor


class BrokenWorkspace:
    def __init__(self, cwd: Path):
        self.cwd = cwd

    def validate(self):
        raise ValueError("method pack front matter is malformed")


def test_doctor_reports_actionable_project_error_instead_of_exception_class(tmp_path, monkeypatch):
    (tmp_path / ".agora").mkdir()
    monkeypatch.setattr("agora_ai_sdlc.doctor.AgoraWorkspace", BrokenWorkspace)
    monkeypatch.setattr("agora_ai_sdlc.doctor.installed_core_version", lambda: "0.9.1")
    monkeypatch.setattr(
        "agora_ai_sdlc.doctor.discover_runtimes",
        lambda root: (),
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.doctor._tool_check",
        lambda command, args=None, timeout=2.0: type(
            "Check",
            (),
            {"id": command, "ok": True, "detail": "ok", "snapshot": lambda self: {}},
        )(),
    )

    checks, _ = run_doctor(tmp_path)

    project = next(item for item in checks if item.id == "project")
    assert project.ok is False
    assert project.detail == "method pack front matter is malformed"


def test_formatter_check_flags_prettier_without_agora_ignore(tmp_path):
    from agora_ai_sdlc.doctor import _formatter_check

    assert _formatter_check(tmp_path) is None
    (tmp_path / "package.json").write_text('{"devDependencies": {"prettier": "^3"}}')
    check = _formatter_check(tmp_path)
    assert check is not None and not check.ok and ".prettierignore" in check.detail
    (tmp_path / ".prettierignore").write_text("dist\n.agora/\n")
    assert _formatter_check(tmp_path).ok
    (tmp_path / ".prettierignore").write_text("dist\n")
    assert not _formatter_check(tmp_path).ok


def test_doctor_uses_single_product_component_ids(tmp_path, monkeypatch):
    monkeypatch.setattr("agora_ai_sdlc.doctor.installed_core_version", lambda: "0.9.1")
    monkeypatch.setattr("agora_ai_sdlc.doctor.discover_runtimes", lambda root: ())
    monkeypatch.setattr(
        "agora_ai_sdlc.doctor._tool_check",
        lambda command, args=None, timeout=2.0: type(
            "Check",
            (),
            {"id": command, "ok": True, "detail": "ok", "snapshot": lambda self: {}},
        )(),
    )
    monkeypatch.setattr("agora_ai_sdlc.doctor.metadata.version", lambda name: "0.3.20")

    checks, _ = run_doctor(tmp_path)
    ids = {item.id for item in checks}

    assert {"agora-flow", "core-kernel", "decision-plane"}.issubset(ids)
    assert "agora-core" not in ids
    assert "laya-system1" not in ids



def test_doctor_reports_chat_first_adapters(tmp_path, monkeypatch):
    (tmp_path / "AGENTS.md").write_text(
        "<!-- agora-flow:agent-discovery:start -->\nCodex\n<!-- agora-flow:agent-discovery:end -->\n",
        encoding="utf-8",
    )
    (tmp_path / "CLAUDE.md").write_text(
        "<!-- agora-flow:agent-discovery:start -->\nClaude\n<!-- agora-flow:agent-discovery:end -->\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("agora_ai_sdlc.doctor.installed_core_version", lambda: "0.9.1")
    monkeypatch.setattr("agora_ai_sdlc.doctor.discover_runtimes", lambda root: ())
    monkeypatch.setattr("agora_ai_sdlc.doctor.metadata.version", lambda name: "0.3.21")

    checks, _ = run_doctor(tmp_path)
    by_id = {item.id: item for item in checks}

    assert by_id["chat-adapter:AGENTS.md"].ok
    assert by_id["chat-adapter:CLAUDE.md"].ok


def test_doctor_marks_missing_chat_adapters_without_breaking_governance(tmp_path, monkeypatch):
    monkeypatch.setattr("agora_ai_sdlc.doctor.installed_core_version", lambda: "0.9.1")
    monkeypatch.setattr("agora_ai_sdlc.doctor.discover_runtimes", lambda root: ())
    monkeypatch.setattr("agora_ai_sdlc.doctor.metadata.version", lambda name: "0.3.21")

    checks, _ = run_doctor(tmp_path)
    by_id = {item.id: item for item in checks}

    assert not by_id["chat-adapter:AGENTS.md"].ok
    assert not by_id["chat-adapter:CLAUDE.md"].ok
    assert "not installed" in by_id["chat-adapter:AGENTS.md"].detail
