import io
import json
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


def test_ollama_runtime_env_configures_opencode_v1_without_mutating_global_env(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(opencode_runner, "_opencode_major_version", lambda **kwargs: 1)
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", '{"theme":"system"}')

    env = opencode_runner._ollama_runtime_env(
        executable="/usr/bin/opencode",
        root=tmp_path,
        model="ollama/qwen3:8b",
    )

    payload = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    assert payload["theme"] == "system"
    assert payload["provider"]["ollama"]["npm"] == "@ai-sdk/openai-compatible"
    assert payload["provider"]["ollama"]["options"]["baseURL"] == "http://127.0.0.1:11434/v1"
    assert "qwen3:8b" in payload["provider"]["ollama"]["models"]


def test_ollama_runtime_env_configures_opencode_v2(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(opencode_runner, "_opencode_major_version", lambda **kwargs: 2)

    env = opencode_runner._ollama_runtime_env(
        executable="/usr/bin/opencode",
        root=tmp_path,
        model="ollama/qwen3:8b",
    )

    payload = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    provider = payload["providers"]["ollama"]
    assert provider["package"] == "aisdk:@ai-sdk/openai-compatible"
    assert provider["settings"]["baseURL"] == "http://127.0.0.1:11434/v1"
    assert provider["models"]["qwen3:8b"]["modelID"] == "qwen3:8b"


def test_list_ollama_models_includes_every_installed_local_model(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["ollama", "list"],
        returncode=0,
        stdout=(
            "NAME                    ID              SIZE      MODIFIED\n"
            "claude:latest           abc123          8 GB      1 hour ago\n"
            "gpt-oss:20b             def456          12 GB     2 hours ago\n"
            "qwen2.5-coder:7b        ghi789          5 GB      3 hours ago\n"
        ),
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)

    models = opencode_runner.list_ollama_models(
        executable="/usr/bin/ollama",
        root=tmp_path,
    )

    assert models == (
        "ollama/claude:latest",
        "ollama/gpt-oss:20b",
        "ollama/qwen2.5-coder:7b",
    )


def test_pull_ollama_model_downloads_and_verifies_installation(monkeypatch, tmp_path: Path):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[1] == "pull":
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(
            command,
            0,
            "NAME ID SIZE MODIFIED\nqwen3:8b abc 5 GB now\n",
            "",
        )

    monkeypatch.setattr(opencode_runner.subprocess, "run", fake_run)

    model = opencode_runner.pull_ollama_model(
        executable="/usr/bin/ollama",
        root=tmp_path,
        model="qwen3:8b",
    )

    assert model == "ollama/qwen3:8b"
    assert commands[0] == ["/usr/bin/ollama", "pull", "qwen3:8b"]
    assert commands[1] == ["/usr/bin/ollama", "list"]


def test_pull_ollama_model_rejects_invalid_name_before_execution(monkeypatch, tmp_path: Path):
    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess must not run for an invalid model name")

    monkeypatch.setattr(opencode_runner.subprocess, "run", fail_run)

    with pytest.raises(RuntimeError, match="Invalid Ollama model name"):
        opencode_runner.pull_ollama_model(
            executable="/usr/bin/ollama",
            root=tmp_path,
            model="qwen3:8b; rm -rf /",
        )


def test_discovers_preferred_free_model_from_configured_models(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["opencode", "models"],
        returncode=0,
        stdout="openai/gpt-5.5\nopencode/mimo-v2.5-free\nopencode/nemotron-3-ultra-free\n",
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)
    monkeypatch.setattr(opencode_runner, "list_ollama_models", lambda **kwargs: ())

    selected = opencode_runner.discover_free_model(
        executable="/usr/bin/opencode",
        root=tmp_path,
    )

    assert selected == "opencode/nemotron-3-ultra-free"


def test_prefers_ollama_even_when_local_alias_looks_like_paid_model(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["opencode", "models"],
        returncode=0,
        stdout="openai/gpt-5.5\nanthropic/claude-sonnet-4\nopencode/nemotron-3-ultra-free\n",
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)
    monkeypatch.setattr(
        opencode_runner,
        "list_ollama_models",
        lambda **kwargs: ("ollama/claude", "ollama/gpt-oss"),
    )

    selected = opencode_runner.discover_free_model(
        executable="/usr/bin/opencode",
        root=tmp_path,
    )

    assert selected == "ollama/claude"


def test_discovers_local_model_missing_from_opencode_models(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["opencode", "models"],
        returncode=0,
        stdout="openai/gpt-5.5\n",
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)
    monkeypatch.setattr(
        opencode_runner,
        "list_ollama_models",
        lambda **kwargs: ("ollama/qwen2.5-coder:7b",),
    )

    selected = opencode_runner.discover_free_model(
        executable="/usr/bin/opencode",
        root=tmp_path,
    )

    assert selected == "ollama/qwen2.5-coder:7b"


def test_free_model_discovery_fails_when_none_is_available(monkeypatch, tmp_path: Path):
    result = subprocess.CompletedProcess(
        args=["opencode", "models"],
        returncode=0,
        stdout="openai/gpt-5.5\n",
        stderr="",
    )
    monkeypatch.setattr(opencode_runner.subprocess, "run", lambda *args, **kwargs: result)
    monkeypatch.setattr(opencode_runner, "list_ollama_models", lambda **kwargs: ())

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
    monkeypatch.setattr(opencode_runner, "_model_runtime_env", lambda **kwargs: {})
    monkeypatch.setattr(opencode_runner, "_validate_selected_model", lambda **kwargs: None)
    monkeypatch.setattr(opencode_runner.subprocess, "Popen", lambda *args, **kwargs: process)

    exit_code = opencode_runner.run_opencode(
        executable="/usr/bin/opencode",
        root=tmp_path,
        model="opencode/nemotron-3-ultra-free",
        prompt="prepare inception",
    )

    assert exit_code == 70
    assert process.killed is True
