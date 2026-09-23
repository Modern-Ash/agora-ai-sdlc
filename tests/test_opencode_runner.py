import io
import subprocess
from pathlib import Path

import pytest

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
    assert opencode_runner.terminal_provider_error("Model not found")
    assert not opencode_runner.terminal_provider_error("temporary network timeout")


def test_discovers_preferred_free_model_from_configured_models(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["opencode", "models"],
        returncode=0,
        stdout=("openai/gpt-5.5\nollama/qwen2.5-coder\nopencode/mimo-v2.5-free\nopencode/nemotron-3-ultra-free\n"),
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)

    selected = opencode_runner.discover_free_model(
        executable="/usr/bin/opencode",
        root=tmp_path,
    )

    assert selected == "ollama/qwen2.5-coder"


def test_prefers_ollama_even_when_local_alias_looks_like_paid_model(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["opencode", "models"],
        returncode=0,
        stdout=(
            "openai/gpt-5.5\nanthropic/claude-sonnet-4\nopencode/nemotron-3-ultra-free\nollama/claude\nollama/gpt-oss\n"
        ),
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)

    selected = opencode_runner.discover_free_model(
        executable="/usr/bin/opencode",
        root=tmp_path,
    )

    assert selected == "ollama/claude"


def test_discovers_local_model_when_no_explicit_free_model_exists(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["opencode", "models"],
        returncode=0,
        stdout="openai/gpt-5.5\nollama/qwen2.5-coder\n",
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)

    selected = opencode_runner.discover_free_model(
        executable="/usr/bin/opencode",
        root=tmp_path,
    )

    assert selected == "ollama/qwen2.5-coder"


def test_free_model_discovery_fails_when_none_is_available(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["opencode", "models"],
        returncode=0,
        stdout="openai/gpt-5.5\n",
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)

    with pytest.raises(RuntimeError, match="no free or local model"):
        opencode_runner.discover_free_model(
            executable="/usr/bin/opencode",
            root=tmp_path,
        )


def test_run_opencode_fails_fast_on_terminal_provider_error(monkeypatch, tmp_path: Path):
    process = FakeProcess(
        "",
        'level=ERROR message="stream error" error.error="AI_APICallError: The usage limit has been reached"\n',
    )
    monkeypatch.setattr(opencode_runner.subprocess, "Popen", lambda *args, **kwargs: process)

    exit_code = opencode_runner.run_opencode(
        executable="/usr/bin/opencode",
        root=tmp_path,
        model="opencode/nemotron-3-ultra-free",
        prompt="prepare inception",
    )

    assert exit_code == 70
    assert process.killed is True
