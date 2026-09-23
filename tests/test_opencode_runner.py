import io
from pathlib import Path

from agora_ai_sdlc import opencode_runner


class FakeStream(io.StringIO):
    pass


class FakeProcess:
    def __init__(self, stdout: str, stderr: str):
        self.stdout = FakeStream(stdout)
        self.stderr = FakeStream(stderr)
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


def test_terminal_provider_error_classification():
    assert opencode_runner.terminal_provider_error('error.error="AI_APICallError: The usage limit has been reached"')
    assert opencode_runner.terminal_provider_error("Monthly usage limit reached")
    assert not opencode_runner.terminal_provider_error("temporary network timeout")


def test_run_opencode_fails_fast_on_terminal_provider_error(monkeypatch, tmp_path: Path):
    process = FakeProcess(
        "",
        'level=ERROR message="stream error" error.error="AI_APICallError: The usage limit has been reached"\n',
    )
    monkeypatch.setattr(opencode_runner.subprocess, "Popen", lambda *args, **kwargs: process)

    exit_code = opencode_runner.run_opencode(
        executable="/usr/bin/opencode",
        root=tmp_path,
        model="opencode/deepseek-v4-flash-free",
        prompt="prepare inception",
    )

    assert exit_code == 70
    assert process.killed is True
