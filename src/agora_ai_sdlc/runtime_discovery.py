"""Credential-free discovery of local AI CLI runtimes."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.i18n import t
from agora_ai_sdlc.runtime_domain import RuntimeKind, RuntimeNormalizationError, normalize_runtime, runtime_kind

RUNTIME_CANDIDATES = (
    ("codex", "Codex", "codex"),
    ("claude", "Claude Code", "claude"),
    ("opencode", "OpenCode", "opencode"),
    ("ollama", "Ollama", "ollama"),
)


@dataclass(frozen=True)
class RuntimeDiscovery:
    id: str
    name: str
    command: str
    installed: bool
    executable: str | None
    responsive: bool
    version: str | None
    configured: bool
    service: str | None = None
    error: str | None = None
    # Model ids a model runtime reports locally (Ollama `list`); never pulled or downloaded.
    models: tuple[str, ...] = ()

    @property
    def kind(self) -> RuntimeKind:
        return runtime_kind(self.id)

    def snapshot(self) -> dict:
        return {**asdict(self), "kind": self.kind.value}


def agent_runtimes(discoveries: tuple[RuntimeDiscovery, ...]) -> tuple[RuntimeDiscovery, ...]:
    return tuple(item for item in discoveries if item.kind is RuntimeKind.AGENT)


def model_runtimes(discoveries: tuple[RuntimeDiscovery, ...]) -> tuple[RuntimeDiscovery, ...]:
    """Model runtimes never satisfy an agent-execution requirement on their own."""
    return tuple(item for item in discoveries if item.kind is RuntimeKind.MODEL)


def _run(
    command: list[str],
    *,
    timeout_seconds: float,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, str | None, str | None]:
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, None, "timeout"
    except OSError as error:
        return False, None, error.__class__.__name__

    output = (result.stdout or result.stderr or "").strip().splitlines()
    version = output[0].strip() if output else None
    if result.returncode != 0:
        return False, version, f"exit-{result.returncode}"
    return True, version, None


def _list_models(
    executable: str,
    *,
    timeout_seconds: float,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[str, ...]:
    """Local model catalog through a normal `ollama list`; no credentials, no pulls."""
    try:
        result = runner([executable, "list"], capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return ()
    if result.returncode != 0:
        return ()
    names = [line.split()[0] for line in (result.stdout or "").splitlines()[1:] if line.strip()]
    return tuple(sorted(dict.fromkeys(names)))


def _configured_runtime_ids(root: Path) -> set[str]:
    configured: set[str] = set()
    try:
        workspace = AgoraWorkspace(cwd=root)
        for actor in workspace.list_actors():
            if getattr(actor, "kind", None) != "ai-agent":
                continue
            values = {
                str(getattr(actor, "id", "") or "").casefold(),
                str(getattr(actor, "name", "") or "").casefold(),
                str(getattr(actor, "integration", "") or "").casefold(),
                str(getattr(actor, "provider", "") or "").casefold(),
            }
            for runtime_id, _, _ in RUNTIME_CANDIDATES:
                if (
                    runtime_id in values
                    or f"ai-{runtime_id}" in values
                    or any(value.endswith(f"-{runtime_id}") for value in values)
                ):
                    configured.add(runtime_id)
    except (OSError, ValueError):
        pass

    metadata = root / "ai-sdlc" / "project.yaml"
    if metadata.is_file():
        try:
            payload = yaml.safe_load(metadata.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            payload = {}
        for runtime in payload.get("runtimes") or []:
            if not isinstance(runtime, dict):
                continue
            try:
                binding = normalize_runtime(runtime)
            except RuntimeNormalizationError:
                binding = None
            if binding is not None:
                configured.add(binding.agent.id.casefold())
                if binding.model is not None and binding.model.id.casefold() in {
                    item[0] for item in RUNTIME_CANDIDATES
                }:
                    configured.add(binding.model.id.casefold())
                continue
            runtime_id = str(runtime.get("id") or "").casefold()
            provider = str(runtime.get("provider") or "").casefold()
            integration = str(runtime.get("integration") or "").casefold()
            for candidate_id, _, _ in RUNTIME_CANDIDATES:
                if candidate_id in {runtime_id, provider, integration}:
                    configured.add(candidate_id)
    return configured


def discover_runtimes(
    root: Path,
    *,
    timeout_seconds: float = 2.0,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[RuntimeDiscovery, ...]:
    """Discover known local CLIs without reading credentials or mutating configuration."""

    configured = _configured_runtime_ids(root)
    discoveries: list[RuntimeDiscovery] = []

    for runtime_id, name, command in RUNTIME_CANDIDATES:
        executable = which(command)
        if executable is None:
            discoveries.append(
                RuntimeDiscovery(
                    id=runtime_id,
                    name=name,
                    command=command,
                    installed=False,
                    executable=None,
                    responsive=False,
                    version=None,
                    configured=runtime_id in configured,
                )
            )
            continue

        responsive, version, error = _run(
            [executable, "--version"],
            timeout_seconds=timeout_seconds,
            runner=runner,
        )
        service = None
        models: tuple[str, ...] = ()
        if runtime_id == "ollama" and responsive:
            daemon_ok, _, daemon_error = _run(
                [executable, "ps"],
                timeout_seconds=timeout_seconds,
                runner=runner,
            )
            service = "responsive" if daemon_ok else f"unavailable:{daemon_error or 'unknown'}"
            if daemon_ok:
                models = _list_models(executable, timeout_seconds=timeout_seconds, runner=runner)

        discoveries.append(
            RuntimeDiscovery(
                id=runtime_id,
                name=name,
                command=command,
                installed=True,
                executable=executable,
                responsive=responsive,
                version=version,
                configured=runtime_id in configured,
                service=service,
                error=error,
                models=models,
            )
        )

    return tuple(discoveries)


def render_runtimes(discoveries: tuple[RuntimeDiscovery, ...], *, lang: str = "en") -> str:
    lines = [t("runtime.title", lang=lang), ""]
    for item in discoveries:
        if not item.installed:
            marker = "-"
            state = t("runtime.not_installed", lang=lang)
        elif item.responsive:
            marker = "✓"
            state = t("runtime.installed_responsive", lang=lang)
        else:
            marker = "!"
            state = t("runtime.installed_failed", lang=lang)
        if item.configured:
            state += " · " + t("runtime.configured", lang=lang)
        if item.kind is RuntimeKind.MODEL:
            state += " · " + t("runtime.kind_model", lang=lang)
        if item.service is not None:
            state += f" · {t('runtime.service', lang=lang)} {item.service}"
        lines.append(f"{marker} {item.name:<12} {state}")
        if item.installed and item.executable:
            lines.append(f"  {item.executable}")
        if item.version:
            lines.append(f"  {item.version}")
        if item.error:
            lines.append(f"  {t('runtime.probe', lang=lang)}: {item.error}")

    lines.extend(
        [
            "",
            t("runtime.credential_note", lang=lang),
            t("runtime.enable_note", lang=lang),
        ]
    )
    return "\n".join(lines)
