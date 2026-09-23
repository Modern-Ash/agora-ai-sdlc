"""Fail-fast supervisor for non-interactive OpenCode execution."""

from __future__ import annotations

import argparse
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import TextIO

from agora_ai_sdlc.llm_failures import recoverable_llm_failure

MODEL_DISCOVERY_TIMEOUT_SECONDS = 15
PREFERRED_FREE_MODELS = (
    "opencode/nemotron-3-ultra-free",
    "opencode/deepseek-v4-flash-free",
    "opencode/mimo-v2.5-free",
)
LOCAL_FREE_PREFIXES = ("ollama/", "lmstudio/")


def terminal_provider_error(line: str) -> bool:
    return recoverable_llm_failure(line)


def _normalize_diagnostic(text: str) -> str:
    return " ".join(text.split())


def _available_models(output: str) -> list[str]:
    models = []
    for raw in output.splitlines():
        value = raw.strip()
        if "/" in value and not any(character.isspace() for character in value):
            models.append(value)
    return models


def _free_model_rank(model: str) -> tuple[int, int | str]:
    normalized = model.casefold()
    if normalized.startswith(LOCAL_FREE_PREFIXES):
        return (0, normalized)
    try:
        return (1, PREFERRED_FREE_MODELS.index(normalized))
    except ValueError:
        pass
    if "free" in normalized:
        return (2, normalized)
    return (3, normalized)


def list_available_models(*, executable: str, root: Path) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            [executable, "models"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=MODEL_DISCOVERY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"Cannot list OpenCode models: {error}") from error

    if result.returncode != 0:
        detail = _normalize_diagnostic(result.stderr or result.stdout)
        raise RuntimeError(f"Cannot list OpenCode models: {detail or 'unknown error'}")

    return tuple(_available_models(result.stdout))


def list_ollama_models(
    *,
    root: Path,
    executable: str | None = None,
) -> tuple[str, ...]:
    command = executable or shutil.which("ollama")
    if not command:
        return ()
    try:
        result = subprocess.run(
            [command, "list"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=MODEL_DISCOVERY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"Cannot list Ollama models: {error}") from error

    if result.returncode != 0:
        detail = _normalize_diagnostic(result.stderr or result.stdout)
        raise RuntimeError(f"Cannot list Ollama models: {detail or 'unknown error'}")

    models: list[str] = []
    for raw in result.stdout.splitlines():
        value = raw.strip()
        if not value:
            continue
        name = value.split()[0]
        if name.casefold() == "name":
            continue
        models.append(f"ollama/{name}")
    return tuple(dict.fromkeys(models))


def discover_free_model(*, executable: str, root: Path) -> str:
    models = list(list_available_models(executable=executable, root=root))
    try:
        models.extend(list_ollama_models(root=root))
    except RuntimeError:
        pass
    models = list(dict.fromkeys(models))
    free_models = [
        model for model in models if "free" in model.casefold() or model.casefold().startswith(LOCAL_FREE_PREFIXES)
    ]
    if not free_models:
        raise RuntimeError(
            "OpenCode has no free or local model available in the current project. "
            "Configure Ollama/LM Studio or a free provider and verify it with 'opencode models'. "
            "Paid Anthropic Claude and OpenAI GPT models are not selected automatically."
        )
    return min(free_models, key=_free_model_rank)


def _pump(stream: TextIO, name: str, events: queue.Queue[tuple[str, str | None]]) -> None:
    try:
        for line in iter(stream.readline, ""):
            events.put((name, line))
    finally:
        events.put((name, None))


def run_opencode(
    *,
    executable: str,
    root: Path,
    prompt: str,
    model: str | None = None,
) -> int:
    try:
        selected_model = model or discover_free_model(executable=executable, root=root)
    except RuntimeError as error:
        print(f"OpenCode free model selection failed: {error}", file=sys.stderr)
        return 69

    print(f"OpenCode free model selected: {selected_model}", file=sys.stderr)
    command = [
        executable,
        "--print-logs",
        "--log-level",
        "ERROR",
        "run",
        "--auto",
        "--model",
        selected_model,
        "--dir",
        str(root.resolve()),
        prompt,
    ]
    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    events: queue.Queue[tuple[str, str | None]] = queue.Queue()
    threads = [
        threading.Thread(target=_pump, args=(process.stdout, "stdout", events), daemon=True),
        threading.Thread(target=_pump, args=(process.stderr, "stderr", events), daemon=True),
    ]
    for thread in threads:
        thread.start()

    closed: set[str] = set()
    fatal: str | None = None
    try:
        while len(closed) < 2:
            name, line = events.get()
            if line is None:
                closed.add(name)
                continue
            target = sys.stdout if name == "stdout" else sys.stderr
            target.write(line)
            target.flush()
            if name == "stderr" and terminal_provider_error(line):
                fatal = _normalize_diagnostic(line)
                if process.poll() is None:
                    process.kill()
                break
    finally:
        if fatal is not None or (process.poll() is None and len(closed) == 2):
            process.wait()

    if fatal is not None:
        print(f"OpenCode terminal provider error: {fatal}", file=sys.stderr)
        return 70
    return process.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--model")
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args(argv)
    return run_opencode(
        executable=args.executable,
        root=Path(args.root),
        model=args.model,
        prompt=args.prompt,
    )


if __name__ == "__main__":
    raise SystemExit(main())
