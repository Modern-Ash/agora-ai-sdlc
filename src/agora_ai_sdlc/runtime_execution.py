"""End-to-end runtime planning from governed Work state to a native RuntimeAdapter.

This module is the product path for AI execution.  Core owns authority, Laya is advisory,
runtime admission is deterministic, and adapters only transport a validated envelope.
"""

from __future__ import annotations

import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_envelope import build_envelope, snapshot_from_workspace
from agora_ai_sdlc.execution_requirements import ExecutionRequirements, requirements_for
from agora_ai_sdlc.iteration_status import inspect_iteration
from agora_ai_sdlc.laya_provider import LayaDecisionProvider
from agora_ai_sdlc.runtime_adapter import sync_projection
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding, normalize_runtime

MAX_GUIDANCE_CHARS = 32_000
_CANONICAL_AGENT_BY_INTEGRATION = {
    "claude": "claude",
    "claude-code": "claude",
    "codex": "codex",
    "opencode": "opencode",
}
_NATIVE_PROVIDER = {"claude": "anthropic", "codex": "openai"}


class RuntimeExecutionError(ValueError):
    """Stable runtime-planning failure raised before Core starts a Session."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class RuntimeExecutionPlan:
    actor_reference: str
    binding: RuntimeBinding
    requirements: ExecutionRequirements
    envelope_path: str
    runner: str
    runtime_name: str
    runtime_version: str | None


def _project_runtime_entries(root: Path) -> tuple[dict[str, Any], ...]:
    path = root / "ai-sdlc" / "project.yaml"
    if not path.is_file():
        return ()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ()
    runtimes = payload.get("runtimes") if isinstance(payload, dict) else None
    if not isinstance(runtimes, list):
        return ()
    return tuple(item for item in runtimes if isinstance(item, dict))


def _canonical_binding(binding: RuntimeBinding) -> RuntimeBinding:
    integration = binding.agent.integration.casefold()
    canonical = _CANONICAL_AGENT_BY_INTEGRATION.get(integration, binding.agent.id.casefold())
    if canonical == binding.agent.id:
        return binding
    return RuntimeBinding(AgentRuntimeRef(canonical, binding.agent.integration), binding.model)


def _configured_bindings(root: Path) -> tuple[tuple[str, RuntimeBinding], ...]:
    values: list[tuple[str, RuntimeBinding]] = []
    for entry in _project_runtime_entries(root):
        label = str(entry.get("id") or "").strip()
        if not label and isinstance(entry.get("agent"), dict):
            label = str(entry["agent"].get("id") or "").strip()
        try:
            binding = _canonical_binding(normalize_runtime(entry))
        except (TypeError, ValueError):
            continue
        values.append((label or binding.agent.id, binding))
    return tuple(values)


def _override_model(binding: RuntimeBinding, model: str) -> RuntimeBinding:
    value = model.strip()
    if not value:
        return binding
    if "/" in value:
        provider, model_id = value.split("/", 1)
        if not provider or not model_id:
            raise RuntimeExecutionError("runtime.model", f"invalid provider/model binding {model!r}")
        runtime_id = "ollama" if provider.casefold() == "ollama" else binding.agent.id
        selected = ModelRuntimeRef(runtime_id, provider, model_id)
    elif binding.model is not None:
        selected = ModelRuntimeRef(binding.model.id, binding.model.provider, value)
    else:
        provider = _NATIVE_PROVIDER.get(binding.agent.id)
        if provider is None:
            raise RuntimeExecutionError(
                "runtime.model_provider",
                f"runtime {binding.agent.id!r} needs an explicit provider/model value",
            )
        selected = ModelRuntimeRef(binding.agent.id, provider, value)
    return RuntimeBinding(binding.agent, selected)


def resolve_runtime_binding(root: Path, runtime_id: str, model: str | None = None) -> RuntimeBinding:
    """Resolve one requested runtime through canonical project configuration.

    Legacy aliases (for example id=primary, integration=codex) remain readable, but the
    returned AgentRuntimeRef always uses the canonical agent id.
    """

    requested = runtime_id.strip().casefold()
    for label, binding in _configured_bindings(root):
        aliases = {
            label.casefold(),
            binding.agent.id.casefold(),
            binding.agent.integration.casefold(),
            _CANONICAL_AGENT_BY_INTEGRATION.get(binding.agent.integration.casefold(), ""),
        }
        if requested in aliases:
            return _override_model(binding, model) if model else binding

    integration = "claude-code" if requested == "claude" else requested
    if requested not in {"claude", "codex", "opencode"}:
        raise RuntimeExecutionError("runtime.agent_unknown", f"no configured agent runtime matches {runtime_id!r}")
    binding = RuntimeBinding(AgentRuntimeRef(requested, integration), None)
    if model:
        return _override_model(binding, model)
    provider = _NATIVE_PROVIDER.get(requested)
    if provider is not None:
        return RuntimeBinding(binding.agent, ModelRuntimeRef(requested, provider, "configured-default"))
    raise RuntimeExecutionError(
        "runtime.model_required",
        "OpenCode requires an explicit provider/model binding (for example ollama/qwen2.5-coder)",
    )


def configured_runtime_for_role(root: Path, role: str, *, requested: str | None = None) -> str:
    """Resolve the configured runtime id for a role without deriving it from an actor name."""

    if requested:
        return requested
    path = root / "ai-sdlc" / "project.yaml"
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        payload = {}
    role_execution = payload.get("role_execution") if isinstance(payload, dict) else None
    runtime_id = role_execution.get(role) if isinstance(role_execution, dict) else None
    if isinstance(runtime_id, str) and runtime_id and runtime_id != "human":
        return runtime_id
    raise RuntimeExecutionError(
        "runtime.role_unbound",
        f"no AI runtime is configured for role {role!r}; pass an explicit --agent",
    )


def _actor_reference(workspace: AgoraWorkspace, actor_id: str) -> str:
    requested = actor_id.strip()
    for actor in workspace.list_actors():
        reference = str(getattr(actor, "reference", "") or "")
        plain_id = str(getattr(actor, "id", "") or "")
        if requested in {reference, plain_id, reference.removeprefix("project:")}:
            return reference
    raise RuntimeExecutionError("runtime.actor_missing", f"Core actor {actor_id!r} does not exist")


def _relative(root: Path, value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return value


def _availability(root: Path) -> dict[str, RuntimeDiscovery]:
    return {item.id: item for item in discover_runtimes(root)}


def _runtime_observation(binding: RuntimeBinding, availability: dict[str, RuntimeDiscovery]) -> RuntimeDiscovery:
    observed = availability.get(binding.agent.id)
    if observed is None or not (observed.installed and observed.responsive):
        raise RuntimeExecutionError(
            "runtime.integration_unavailable",
            f"agent runtime {binding.agent.id!r} is not installed and responsive",
        )
    return observed


def persist_envelope(root: Path, work: str, payload: dict[str, Any]) -> Path:
    target = root / ".agora" / "ai-sdlc" / "execution" / work / "EXECUTION_ENVELOPE.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def adapter_runner_command(root: Path, envelope_path: Path) -> str:
    relative = envelope_path.resolve().relative_to(root.resolve()).as_posix()
    return shlex.join(
        [
            sys.executable,
            "-m",
            "agora_ai_sdlc.adapter_runner",
            "--root",
            str(root.resolve()),
            "--envelope",
            relative,
        ]
    )


def prepare_runtime_execution(
    root: Path,
    bundle: ExecutionBundle,
    *,
    actor_id: str,
    runtime_id: str,
    model: str | None,
    guidance: str,
    workspace_factory=AgoraWorkspace,
    use_laya: bool = True,
    sync_native_projection: bool = True,
) -> RuntimeExecutionPlan:
    """Build, admit and persist the exact execution envelope used by a Core Session."""

    root = root.resolve()
    if len(guidance) > MAX_GUIDANCE_CHARS:
        raise RuntimeExecutionError(
            "runtime.context_too_large",
            f"bounded execution guidance exceeds {MAX_GUIDANCE_CHARS} characters; reduce context before launch",
        )
    workspace = workspace_factory(cwd=root)
    actor_reference = _actor_reference(workspace, actor_id)
    status = inspect_iteration(root, swarm=bundle.swarm, work=bundle.work)
    if status.work != bundle.work or status.swarm != bundle.swarm:
        raise RuntimeExecutionError("runtime.scope_changed", "Core Work scope changed before runtime planning")
    snapshot = snapshot_from_workspace(workspace, status)

    provider = LayaDecisionProvider() if use_laya else None
    requirements = requirements_for(bundle, provider=provider)
    binding = resolve_runtime_binding(root, runtime_id, model)
    availability = _availability(root)
    observed = _runtime_observation(binding, availability)

    bundle_ref = _relative(root, bundle.markdown_path or bundle.json_path)
    context = {
        "kind": "bounded-execution-guidance",
        "guidance": guidance,
        "bundle": bundle_ref,
        "authoritative": False,
    }
    envelope = build_envelope(
        snapshot,
        requirements,
        binding,
        bundle,
        actor_id=actor_reference,
        availability=availability,
        context=context,
    )
    if not envelope.executable:
        raise RuntimeExecutionError(
            "runtime.human_boundary",
            "Core reports a human authority boundary; an AI executor cannot be launched",
        )

    registry = default_registry(root)
    adapter = registry.get(binding.agent)
    health = adapter.health()
    if not (health.installed and health.responsive):
        raise RuntimeExecutionError(
            "runtime.adapter_unavailable",
            f"{binding.agent.id} adapter cannot launch: {health.detail or 'runtime unavailable'}",
        )
    if sync_native_projection:
        sync_projection(root, adapter.plan_projection(("instructions",)))

    path = persist_envelope(root, bundle.work, envelope.to_dict())
    return RuntimeExecutionPlan(
        actor_reference=actor_reference,
        binding=binding,
        requirements=requirements,
        envelope_path=str(path),
        runner=adapter_runner_command(root, path),
        runtime_name=observed.name,
        runtime_version=observed.version,
    )
