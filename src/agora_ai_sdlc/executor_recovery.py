"""Interactive recovery after a recoverable executor/provider failure."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, TypeVar

from agora_ai_sdlc.executor_launch import executor_capable
from agora_ai_sdlc.opencode_runner import LOCAL_FREE_PREFIXES, list_available_models
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes


T = TypeVar("T")


@dataclass(frozen=True)
class ExecutorRecoveryCancelled(ValueError):
    """Human declined to retry an LLM-backed step with another runtime/model."""


@dataclass(frozen=True)
class ExecutorRecoveryChoice:
    agent: str
    model: str | None
    label: str


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


def recovery_choices(
    root: Path,
    *,
    discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
    model_lister: Callable[..., tuple[str, ...]] = list_available_models,
) -> tuple[ExecutorRecoveryChoice, ...]:
    choices: list[ExecutorRecoveryChoice] = []
    runtimes = [
        item
        for item in discovery(root)
        if item.installed and item.responsive and executor_capable(item.id)
    ]

    opencode = next((item for item in runtimes if item.id == "opencode"), None)
    if opencode is not None:
        try:
            models = model_lister(
                executable=opencode.executable or opencode.command,
                root=root,
            )
        except RuntimeError:
            models = ()
        for model in sorted(models, key=_model_rank):
            choices.append(
                ExecutorRecoveryChoice(
                    agent="opencode",
                    model=model,
                    label=f"OpenCode · {model} [{_model_badge(model)}]",
                )
            )

    for runtime in runtimes:
        if runtime.id == "opencode":
            continue
        choices.append(
            ExecutorRecoveryChoice(
                agent=runtime.id,
                model=None,
                label=f"{runtime.name} · configured model",
            )
        )

    return tuple(choices)


@dataclass(frozen=True)
class RecoveryFailureContext:
    workspace_root: Path
    message: str
    recoverable: bool


def prompt_executor_recovery(
    root: Path,
    *,
    error: str,
    input_stream: TextIO,
    output_stream: TextIO,
    lang: str = "en",
    discovery: Callable[[Path], tuple[RuntimeDiscovery, ...]] = discover_runtimes,
    model_lister: Callable[..., tuple[str, ...]] = list_available_models,
) -> ExecutorRecoveryChoice | None:
    choices = recovery_choices(
        root,
        discovery=discovery,
        model_lister=model_lister,
    )
    if lang == "es":
        print(f"\nEl LLM/proveedor falló: {error}", file=output_stream)
        print("Elegí otro LLM/modelo para reintentar:", file=output_stream)
        cancel = "Cancelar"
        invalid = "Opción inválida."
    else:
        print(f"\nThe LLM/provider failed: {error}", file=output_stream)
        print("Choose another LLM/model to retry:", file=output_stream)
        cancel = "Cancel"
        invalid = "Invalid option."

    if not choices:
        print("  (no alternatives detected)", file=output_stream)
        return None

    for index, choice in enumerate(choices, start=1):
        print(f"  {index}) {choice.label}", file=output_stream)
    print(f"  0) {cancel}", file=output_stream)
    output_stream.flush()

    while True:
        line = input_stream.readline()
        if line == "":
            return None
        value = line.strip()
        if value == "0":
            return None
        try:
            index = int(value)
        except ValueError:
            print(invalid, file=output_stream)
            output_stream.flush()
            continue
        if 1 <= index <= len(choices):
            return choices[index - 1]
        print(invalid, file=output_stream)
        output_stream.flush()



def run_with_recovery(
    operation: Callable[[str | None, str | None], T],
    *,
    initial_agent: str | None,
    initial_model: str | None,
    interactive: bool,
    input_stream: TextIO,
    output_stream: TextIO,
    lang: str,
    failure_context: Callable[[BaseException], RecoveryFailureContext | None],
) -> T:
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
