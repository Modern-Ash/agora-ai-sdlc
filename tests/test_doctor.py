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
