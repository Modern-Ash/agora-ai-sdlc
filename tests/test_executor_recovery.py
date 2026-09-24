import io
from pathlib import Path

from agora_ai_sdlc import executor_recovery
from agora_ai_sdlc.executor_recovery import (
    ExecutorRecoveryChoice,
    RecoveryFailureContext,
    prompt_executor_recovery,
    recovery_choices,
    recovery_groups,
    run_with_recovery,
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
        runtime("ollama", "Ollama"),
        runtime("claude", "Claude Code"),
        runtime("codex", "Codex"),
    )


def models(**_kwargs) -> tuple[str, ...]:
    return (
        "openai/gpt-5.5",
        "opencode/nemotron-3-ultra-free",
        "opencode/big-pickle",
    )


def ollama_models(**_kwargs) -> tuple[str, ...]:
    return (
        "ollama/claude:latest",
        "ollama/gpt-oss:20b",
        "ollama/qwen2.5-coder:7b",
    )


def test_recovery_groups_split_provider_from_model_and_include_all_ollama(tmp_path: Path):
    groups = recovery_groups(
        tmp_path,
        discovery=discoveries,
        model_lister=models,
        ollama_model_lister=ollama_models,
    )

    assert [group.id for group in groups] == [
        "ollama",
        "opencode",
        "openai",
        "claude",
        "codex",
    ]
    assert groups[0].models == (
        "ollama/claude:latest",
        "ollama/gpt-oss:20b",
        "ollama/qwen2.5-coder:7b",
    )
    assert groups[1].models == (
        "opencode/nemotron-3-ultra-free",
        "opencode/big-pickle",
    )


def test_recovery_choices_still_expose_final_agent_model_pairs(tmp_path: Path):
    choices = recovery_choices(
        tmp_path,
        discovery=discoveries,
        model_lister=models,
        ollama_model_lister=ollama_models,
    )

    pairs = [(item.agent, item.model) for item in choices]
    assert ("opencode", "ollama/claude:latest") in pairs
    assert ("opencode", "ollama/gpt-oss:20b") in pairs
    assert ("opencode", "ollama/qwen2.5-coder:7b") in pairs
    assert ("opencode", "opencode/nemotron-3-ultra-free") in pairs
    assert ("opencode", "openai/gpt-5.5") in pairs
    assert ("claude", None) in pairs
    assert ("codex", None) in pairs


def test_prompt_selects_llm_first_and_model_second(tmp_path: Path):
    output = io.StringIO()
    choice = prompt_executor_recovery(
        tmp_path,
        error="usage limit reached",
        input_stream=io.StringIO("1\n2\n"),
        output_stream=output,
        lang="es",
        discovery=discoveries,
        model_lister=models,
        ollama_model_lister=ollama_models,
    )

    assert choice == ExecutorRecoveryChoice(
        agent="opencode",
        model="ollama/gpt-oss:20b",
        label="Ollama (local via OpenCode) · ollama/gpt-oss:20b [local]",
    )
    rendered = output.getvalue()
    assert "Paso 1/2: elegí el LLM/proveedor:" in rendered
    assert "1) Ollama (local via OpenCode)" in rendered
    assert "2) OpenCode" in rendered
    assert "3) OpenAI" in rendered
    assert "Paso 2/2: elegí el modelo para Ollama (local via OpenCode):" in rendered
    assert "claude:latest [local]" in rendered
    assert "gpt-oss:20b [local]" in rendered
    assert "qwen2.5-coder:7b [local]" in rendered
    assert "gpt-5.5" not in rendered


def test_prompt_can_pull_and_select_new_ollama_model(tmp_path: Path):
    output = io.StringIO()
    pulled = []

    def puller(**kwargs):
        pulled.append(kwargs["model"])
        return "ollama/qwen3:8b"

    choice = prompt_executor_recovery(
        tmp_path,
        error="model not found",
        input_stream=io.StringIO("1\n4\nqwen3:8b\n"),
        output_stream=output,
        lang="es",
        discovery=discoveries,
        model_lister=models,
        ollama_model_lister=ollama_models,
        ollama_model_puller=puller,
    )

    assert pulled == ["qwen3:8b"]
    assert choice == ExecutorRecoveryChoice(
        agent="opencode",
        model="ollama/qwen3:8b",
        label="Ollama (local via OpenCode) · ollama/qwen3:8b [local]",
    )
    rendered = output.getvalue()
    assert "Descargar otro modelo con ollama pull" in rendered
    assert "Descargando qwen3:8b con ollama pull" in rendered


def test_failed_ollama_pull_stays_in_model_selector(tmp_path: Path):
    output = io.StringIO()

    def puller(**kwargs):
        raise RuntimeError("Ollama pull failed")

    choice = prompt_executor_recovery(
        tmp_path,
        error="model not found",
        input_stream=io.StringIO("1\n4\nmissing:latest\n0\n0\n"),
        output_stream=output,
        lang="es",
        discovery=discoveries,
        model_lister=models,
        ollama_model_lister=ollama_models,
        ollama_model_puller=puller,
    )

    assert choice is None
    rendered = output.getvalue()
    assert "No se pudo descargar el modelo: Ollama pull failed" in rendered


def test_prompt_zero_cancels_at_provider_step(tmp_path: Path):
    assert (
        prompt_executor_recovery(
            tmp_path,
            error="quota exceeded",
            input_stream=io.StringIO("0\n"),
            output_stream=io.StringIO(),
            lang="es",
            discovery=discoveries,
            model_lister=models,
            ollama_model_lister=ollama_models,
        )
        is None
    )


def test_shared_recovery_loop_retries_any_llm_backed_operation(monkeypatch, tmp_path: Path):
    calls = []

    class ProviderFailure(RuntimeError):
        pass

    def operation(agent, model):
        calls.append((agent, model))
        if len(calls) == 1:
            raise ProviderFailure("quota exceeded")
        return "completed"

    monkeypatch.setattr(
        executor_recovery,
        "prompt_executor_recovery",
        lambda *args, **kwargs: ExecutorRecoveryChoice(
            agent="opencode",
            model="ollama/claude:latest",
            label="Ollama (local via OpenCode) · ollama/claude:latest [local]",
        ),
    )

    result = run_with_recovery(
        operation,
        initial_agent="opencode",
        initial_model="openai/gpt-5.5",
        interactive=True,
        input_stream=io.StringIO(),
        output_stream=io.StringIO(),
        lang="es",
        failure_context=lambda error: RecoveryFailureContext(
            workspace_root=tmp_path,
            message=str(error),
            recoverable=isinstance(error, ProviderFailure),
        ),
    )

    assert result == "completed"
    assert calls == [
        ("opencode", "openai/gpt-5.5"),
        ("opencode", "ollama/claude:latest"),
    ]
