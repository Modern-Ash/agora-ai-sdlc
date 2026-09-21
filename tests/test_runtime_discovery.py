import subprocess

import yaml

from agora_ai_sdlc.runtime_discovery import discover_runtimes, render_runtimes


def test_runtime_discovery_reports_present_missing_and_configured(tmp_path):
    metadata = tmp_path / "ai-sdlc"
    metadata.mkdir()
    (metadata / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "agora-ai-sdlc/project-config/v1",
                "runtimes": [
                    {
                        "id": "codex",
                        "integration": "codex",
                        "provider": "openai",
                        "model": "gpt",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    paths = {
        "codex": "/bin/codex",
        "claude": "/bin/claude",
        "ollama": "/bin/ollama",
    }

    def which(command):
        return paths.get(command)

    def runner(command, **kwargs):
        if command == ["/bin/codex", "--version"]:
            return subprocess.CompletedProcess(command, 0, stdout="codex 1.2.3\n", stderr="")
        if command == ["/bin/claude", "--version"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="broken\n")
        if command == ["/bin/ollama", "--version"]:
            return subprocess.CompletedProcess(command, 0, stdout="ollama version 0.9\n", stderr="")
        if command == ["/bin/ollama", "ps"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="daemon unavailable\n")
        raise AssertionError(command)

    result = discover_runtimes(tmp_path, which=which, runner=runner)
    by_id = {item.id: item for item in result}

    assert by_id["codex"].installed is True
    assert by_id["codex"].responsive is True
    assert by_id["codex"].configured is True
    assert by_id["codex"].version == "codex 1.2.3"

    assert by_id["claude"].installed is True
    assert by_id["claude"].responsive is False
    assert by_id["claude"].error == "exit-1"

    assert by_id["opencode"].installed is False
    assert by_id["ollama"].service == "unavailable:exit-1"

    output = render_runtimes(result)
    assert "Codex" in output
    assert "configured" in output
    assert "installation does not imply authentication" in output


def test_runtime_discovery_handles_timeout(tmp_path):
    def which(command):
        return "/bin/codex" if command == "codex" else None

    def runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 2)

    result = discover_runtimes(tmp_path, which=which, runner=runner)
    codex = result[0]

    assert codex.installed is True
    assert codex.responsive is False
    assert codex.error == "timeout"


def test_runtime_discovery_is_deterministic(tmp_path):
    result = discover_runtimes(tmp_path, which=lambda command: None)
    assert [item.id for item in result] == ["codex", "claude", "opencode", "ollama"]
    assert all(item.installed is False for item in result)
