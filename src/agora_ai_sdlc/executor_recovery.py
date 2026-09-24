"""Interactive recovery after a recoverable executor/provider failure."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agora_ai_sdlc.executor_launch import executor_capable
from agora_ai_sdlc.opencode_runner import (
    LOCAL_FREE_PREFIXES,
    list_available_models,
    list_ollama_agent_models,
    pull_ollama_model,
)
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes


class ExecutorRecoveryCancelled(ValueError):
    """Human declined to retry an LLM-backed step with another runtime/model."""


@dataclass(frozen=True)
class ExecutorRecoveryChoice:
    agent: str
    model: str | None
    label: str


@dataclass(frozen=True)
class ExecutorModelGroup:
    id: str
    label: str
    agent: str
    models: tuple[str | None, ...]


@dataclass(frozen=True)
class RecoveryFailureContext:
    workspace_root: Path
    message: str
    recoverable: bool


def _provider_id(model: str) -> str:
    return model.split("/", 1)[0].casefold()


def _provider_label(provider: str) -> str:
    labels = {
        "ollama": "Ollama (local via OpenCode)",
        "opencode": "OpenCode",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google",
        "gemini": "Gemini",
        "lmstudio": "LM Studio (local)",
    }
    return labels.get(provider, provider.replace("-", " ").title())


def _provider_rank(provider: str) -> tuple[int, str]:
    if provider == "ollama":
        return (0, provider)
    if provider == "lmstudio":
        return (1, provider)
    if provider == "opencode":
        return (2, provider)
    return (3, provider)


def _model_rank(model: str) -> tuple[int, str]:
    normalized = model.casefold()
    if normalized.startswith(LOCAL_FREE_PREFIXES):
        return (0, normalized)
    if "free" in normalized:
        return (1, normalized)
    return (2, normalized)


def _model_badge(model: str) -> str:
    normalized = model.casefold()
    if normalized.startswith(LOCAL_FREE_PREFIXES):
        return "local"
    if "free" in normalized:
        return "free"
    return "external"


def _model_display(model: str) -> str:
    return model.split("/", 1)[1] if "/" in model else model


def recovery_groups(
    root: Path,
    *,
    discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
    model_lister: Callable[..., tuple[str, ...]] = list_available_models,
    ollama_model_lister: Callable[..., tuple[str, ...]] = list_ollama_agent_models,
) -> tuple[ExecutorModelGroup, ...]:
    discovered = tuple(discovery(root))
    executors = [item for item in discovered if item.installed and item.responsive and executor_capable(item.id)]
    groups: list[ExecutorModelGroup] = []

    opencode = next((item for item in executors if item.id == "opencode"), None)
    if opencode is not None:
        models: list[str] = []
        try:
            models.extend(
                model
                for model in model_lister(
                    executable=opencode.executable or opencode.command,
                    root=root,
                )
                if not model.casefold().startswith("ollama/")
            )
        except RuntimeError:
            pass

        ollama = next(
            (item for item in discovered if item.id == "ollama" and item.installed and item.responsive),
            None,
        )
        try:
            models.extend(
                ollama_model_lister(
                    root=root,
                    executable=(ollama.executable or ollama.command) if ollama else None,
                )
            )
        except RuntimeError:
            pass

        by_provider: dict[str, list[str]] = {}
        for model in dict.fromkeys(models):
            if "/" not in model:
                continue
            by_provider.setdefault(_provider_id(model), []).append(model)

        for provider in sorted(by_provider, key=_provider_rank):
            provider_models = tuple(sorted(by_provider[provider], key=_model_rank))
            groups.append(
                ExecutorModelGroup(
                    id=provider,
                    label=_provider_label(provider),
                    agent="opencode",
                    models=provider_models,
                )
            )

    for runtime in executors:
        if runtime.id == "opencode":
            continue
        groups.append(
            ExecutorModelGroup(
                id=runtime.id,
                label=runtime.name,
                agent=runtime.id,
                models=(None,),
            )
        )

    return tuple(groups)


def recovery_choices(
    root: Path,
    *,
    discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
    model_lister: Callable[..., tuple[str, ...]] = list_available_models,
    ollama_model_lister: Callable[..., tuple[str, ...]] = list_ollama_agent_models,
) -> tuple[ExecutorRecoveryChoice, ...]:
    choices: list[ExecutorRecoveryChoice] = []
    for group in recovery_groups(
        root,
        discovery=discovery,
        model_lister=model_lister,
        ollama_model_lister=ollama_model_lister,
    ):
        for model in group.models:
            if model is None:
                label = f"{group.label} · configured model"
            else:
                label = f"{group.label} · {model} [{_model_badge(model)}]"
            choices.append(
                ExecutorRecoveryChoice(
                    agent=group.agent,
                    model=model,
                    label=label,
                )
            )
    return tuple(choices)


def _choose_index(
    *,
    count: int,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    prompt: str,
    invalid: str,
) -> int | None:
    while True:
        value = input_fn(prompt).strip()
        if value == "0":
            return None
        try:
            index = int(value)
        except ValueError:
            output_fn(invalid)
            continue
        if 1 <= index <= count:
            return index - 1
        output_fn(invalid)


def select_executor_model(
    root: Path,
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    current: ExecutorRecoveryChoice | None = None,
    lang: str = "en",
    discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
    model_lister: Callable[..., tuple[str, ...]] = list_available_models,
    ollama_model_lister: Callable[..., tuple[str, ...]] = list_ollama_agent_models,
    ollama_model_puller: Callable[..., str] = pull_ollama_model,
) -> ExecutorRecoveryChoice | None:
    groups = recovery_groups(
        root,
        discovery=discovery,
        model_lister=model_lister,
        ollama_model_lister=ollama_model_lister,
    )
    if not groups:
        output_fn("(no alternatives detected)" if lang == "en" else "(no se detectaron alternativas)")
        return None

    if lang == "es":
        provider_title = "Paso 1/2: elegí el LLM/proveedor:"
        provider_prompt = "LLM/proveedor: "
        model_title = "Paso 2/2: elegí el modelo para {provider}:"
        model_prompt = "Modelo: "
        cancel = "Cancelar"
        back = "Volver"
        configured = "Modelo configurado por {provider}"
        download = "Descargar otro modelo con ollama pull…"
        download_prompt = "Modelo Ollama a descargar (ej. qwen3:8b): "
        downloading = "Descargando {model} con ollama pull…"
        pull_failed = "No se pudo descargar el modelo: {error}"
        invalid = "Opción inválida."
    else:
        provider_title = "Step 1/2: choose the LLM/provider:"
        provider_prompt = "LLM/provider: "
        model_title = "Step 2/2: choose the model for {provider}:"
        model_prompt = "Model: "
        cancel = "Cancel"
        back = "Back"
        configured = "Configured model for {provider}"
        download = "Download another model with ollama pull…"
        download_prompt = "Ollama model to download (e.g. qwen3:8b): "
        downloading = "Downloading {model} with ollama pull…"
        pull_failed = "Could not download model: {error}"
        invalid = "Invalid option."

    while True:
        output_fn("")
        output_fn(provider_title)
        for index, group in enumerate(groups, start=1):
            selected = ""
            if current is not None and (
                (group.agent != "opencode" and current.agent == group.agent)
                or (
                    group.agent == "opencode"
                    and current.agent == "opencode"
                    and current.model is not None
                    and _provider_id(current.model) == group.id
                )
            ):
                selected = " (actual)" if lang == "es" else " (current)"
            output_fn(f"  {index}) {group.label}{selected}")
        output_fn(f"  0) {cancel}")

        group_index = _choose_index(
            count=len(groups),
            input_fn=input_fn,
            output_fn=output_fn,
            prompt=provider_prompt,
            invalid=invalid,
        )
        if group_index is None:
            return current
        group = groups[group_index]

        while True:
            output_fn("")
            output_fn(model_title.format(provider=group.label))
            for index, model in enumerate(group.models, start=1):
                if model is None:
                    label = configured.format(provider=group.label)
                else:
                    label = f"{_model_display(model)} [{_model_badge(model)}]"
                selected = ""
                if current is not None and current.agent == group.agent and current.model == model:
                    selected = " (actual)" if lang == "es" else " (current)"
                output_fn(f"  {index}) {label}{selected}")

            can_pull = group.id == "ollama"
            if can_pull:
                output_fn(f"  {len(group.models) + 1}) {download}")
            output_fn(f"  0) {back}")

            model_index = _choose_index(
                count=len(group.models) + (1 if can_pull else 0),
                input_fn=input_fn,
                output_fn=output_fn,
                prompt=model_prompt,
                invalid=invalid,
            )
            if model_index is None:
                break

            if can_pull and model_index == len(group.models):
                requested = input_fn(download_prompt).strip()
                if not requested:
                    continue
                output_fn(downloading.format(model=requested))
                discovered = tuple(discovery(root))
                ollama = next(
                    (item for item in discovered if item.id == "ollama" and item.installed and item.responsive),
                    None,
                )
                try:
                    model = ollama_model_puller(
                        root=root,
                        model=requested,
                        executable=(ollama.executable or ollama.command) if ollama else None,
                    )
                except RuntimeError as error:
                    output_fn(pull_failed.format(error=error))
                    continue
                return ExecutorRecoveryChoice(
                    agent="opencode",
                    model=model,
                    label=f"{group.label} · {model} [local]",
                )

            model = group.models[model_index]
            if model is None:
                label = f"{group.label} · configured model"
            else:
                label = f"{group.label} · {model} [{_model_badge(model)}]"
            return ExecutorRecoveryChoice(
                agent=group.agent,
                model=model,
                label=label,
            )


def prompt_executor_recovery(
    root: Path,
    *,
    error: str,
    input_stream,
    output_stream,
    lang: str = "en",
    discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
    model_lister: Callable[..., tuple[str, ...]] = list_available_models,
    ollama_model_lister: Callable[..., tuple[str, ...]] = list_ollama_agent_models,
    ollama_model_puller: Callable[..., str] = pull_ollama_model,
) -> ExecutorRecoveryChoice | None:
    if lang == "es":
        print(f"\nEl LLM/proveedor falló: {error}", file=output_stream)
    else:
        print(f"\nThe LLM/provider failed: {error}", file=output_stream)

    def input_fn(prompt: str) -> str:
        print(prompt, end="", file=output_stream)
        output_stream.flush()
        return input_stream.readline()

    def output_fn(message: str) -> None:
        print(message, file=output_stream)
        output_stream.flush()

    return select_executor_model(
        root,
        input_fn=input_fn,
        output_fn=output_fn,
        lang=lang,
        discovery=discovery,
        model_lister=model_lister,
        ollama_model_lister=ollama_model_lister,
        ollama_model_puller=ollama_model_puller,
    )


def run_with_recovery(
    operation: Callable[[str | None, str | None], object],
    *,
    initial_agent: str | None,
    initial_model: str | None,
    interactive: bool,
    input_stream,
    output_stream,
    lang: str,
    failure_context: Callable[[BaseException], RecoveryFailureContext | None],
) -> object:
    """Run any LLM-backed step with one shared human recovery loop."""

    selected_agent = initial_agent
    selected_model = initial_model

    while True:
        try:
            return operation(selected_agent, selected_model)
        except BaseException as error:
            context = failure_context(error)
            if context is None or not context.recoverable or not interactive:
                raise
            choice = prompt_executor_recovery(
                context.workspace_root,
                error=context.message,
                input_stream=input_stream,
                output_stream=output_stream,
                lang=lang,
            )
            if choice is None:
                raise ExecutorRecoveryCancelled("Executor recovery cancelled.") from error
            selected_agent = choice.agent
            selected_model = choice.model
