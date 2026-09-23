import io
from pathlib import Path

from agora_ai_sdlc.executor_recovery import (
    ExecutorRecoveryChoice,
    prompt_executor_recovery,
    recovery_choices,
)
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery


def runtime(runtime_id: str, name: str) -> RuntimeDiscovery:
    return RuntimeDiscovery(
        id=runtime_id,
        name=name,
        command=runtime_id,
        installed=True,
        executable=f"/usr/bin/{runtime_id}",
        responsive=True,
        version="1.0",
        configured=True,
    )


def discoveries(_root: Path) -> tuple[RuntimeDiscovery, ...]:
    return (
        runtime("opencode", "OpenCode"),
        runtime("claude", "Claude Code"),
        runtime("codex", "Codex"),
    )


def models(**_kwargs) -> tuple[str, ...]:
    return (
        "openai/gpt-5.5",
        "opencode/nemotron-3-ultra-free",
        "ollama/claude",
        "ollama/gpt-oss",
    )


def test_recovery_choices_prioritize_local_then_free_then_external_models(tmp_path: Path):
    choices = recovery_choices(
        tmp_path,
        discovery=discoveries,
        model_lister=models,
    )

    assert [(item.agent, item.model) for item in choices[:4]] == [
        ("opencode", "ollama/claude"),
        ("opencode", "ollama/gpt-oss"),
        ("opencode", "opencode/nemotron-3-ultra-free"),
        ("opencode", "openai/gpt-5.5"),
    ]
    assert ("claude", None) in [(item.agent, item.model) for item in choices]
    assert ("codex", None) in [(item.agent, item.model) for item in choices]


def test_prompt_returns_selected_llm_and_model(tmp_path: Path):
    output = io.StringIO()
    choice = prompt_executor_recovery(
        tmp_path,
        error="usage limit reached",
        input_stream=io.StringIO("2\n"),
        output_stream=output,
        lang="es",
        discovery=discoveries,
        model_lister=models,
    )

    assert choice == ExecutorRecoveryChoice(
        agent="opencode",
        model="ollama/gpt-oss",
        label="OpenCode · ollama/gpt-oss [local]",
    )
    rendered = output.getvalue()
    assert "Elegí otro LLM/modelo" in rendered
    assert "ollama/claude [local]" in rendered
    assert "openai/gpt-5.5 [external]" in rendered


def test_prompt_zero_cancels_recovery(tmp_path: Path):
    assert (
        prompt_executor_recovery(
            tmp_path,
            error="quota exceeded",
            input_stream=io.StringIO("0\n"),
            output_stream=io.StringIO(),
            lang="es",
            discovery=discoveries,
            model_lister=models,
        )
        is None
    )
