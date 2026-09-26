"""End-to-end wiring for provider-neutral governed runtime execution.

This module is the single bridge from Agora Flow state to the runtime layer:
Core/GuidedDecision -> ExecutionRequirements (optional Laya) -> RuntimeBinding ->
ExecutionEnvelope -> RuntimeAdapter. Runtime choice never changes Core authority.
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
from agora_ai_sdlc.execution_envelope import CoreSnapshot, ExecutionEnvelope, build_envelope
from agora_ai_sdlc.execution_requirements import ExecutionRequirements, requirements_for
from agora_ai_sdlc.laya_provider import LayaDecisionProvider
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding, normalize_runtime


class RuntimeExecutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class GovernedRuntimePlan:
    envelope: ExecutionEnvelope
    requirements: ExecutionRequirements
    binding: RuntimeBinding
    runtime: RuntimeDiscovery
    actor_reference: str
    actor_id: str
    runner: str
    envelope_path: str


def _project_bindings(root: Path) -> tuple[RuntimeBinding, ...]:
    path = root / "ai-sdlc" / "project.yaml"
    if not path.is_file():
        return ()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ()
    values = payload.get("runtimes") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        return ()
    bindings: list[RuntimeBinding] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        try:
            bindings.append(normalize_runtime(value))
        except ValueError:
            continue
    return tuple(bindings)


def _model_override(runtime_id: str, value: str, current: RuntimeBinding | None) -> ModelRuntimeRef:
    raw = value.strip()
    if not raw:
        raise RuntimeExecutionError("runtime.model.empty", "model override must not be empty")
    if "/" in raw:
        provider, model = raw.split("/", 1)
    elif runtime_id == "claude":
        provider, model = "anthropic", raw
    elif runtime_id == "codex":
        provider, model = "openai", raw
    elif current is not None and current.model is not None:
        provider, model = current.model.provider, raw
    else:
        raise RuntimeExecutionError(
            "runtime.model.provider_required",
            f"runtime {runtime_id!r} requires provider/model syntax for an explicit model",
        )
    if not provider or not model:
        raise RuntimeExecutionError("runtime.model.invalid", f"invalid model override {value!r}")
    model_id = provider if provider.casefold() == "ollama" else provider
    return ModelRuntimeRef(model_id, provider, model)


def binding_for(root: Path, runtime_id: str, model: str | None = None) -> RuntimeBinding:
    """Resolve one explicit agent/model binding without inferring actor identity."""
    configured = next((item for item in _project_bindings(root) if item.agent.id == runtime_id), None)
    if configured is not None:
        if model is None:
            return configured
        return RuntimeBinding(configured.agent, _model_override(runtime_id, model, configured))

    integrations = {"claude": "claude-code", "codex": "codex", "opencode": "opencode"}
    if runtime_id not in integrations:
        raise RuntimeExecutionError("runtime.agent.unknown", f"{runtime_id!r} is not a supported agent runtime")
    agent = AgentRuntimeRef(runtime_id, integrations[runtime_id])
    if model is not None:
        return RuntimeBinding(agent, _model_override(runtime_id, model, None))
    if runtime_id == "claude":
        return RuntimeBinding(agent, ModelRuntimeRef("anthropic", "anthropic", "configured-default"))
    if runtime_id == "codex":
        return RuntimeBinding(agent, ModelRuntimeRef("openai", "openai", "configured-default"))
    raise RuntimeExecutionError(
        "runtime.model.required",
        "OpenCode requires an explicit provider/model binding; configure it in ai-sdlc/project.yaml "
        "or pass --model provider/model",
    )


def runtime_for(root: Path, runtime_id: str) -> RuntimeDiscovery:
    for item in discover_runtimes(root):
        if item.id == runtime_id and item.installed and item.responsive:
            return item
    raise RuntimeExecutionError(
        "runtime.unavailable", f"agent runtime {runtime_id!r} is not installed and responsive"
    )


def _actor_reference(workspace: Any, requested: str | None) -> tuple[str, str]:
    if not requested:
        raise RuntimeExecutionError("runtime.actor.missing", "Core reports no responsible actor")
    wanted = requested.removeprefix("project:")
    for actor in workspace.list_actors():
        actor_id = str(getattr(actor, "id", "") or "")
        reference = str(getattr(actor, "reference", "") or "")
        if requested in {actor_id, reference} or wanted == actor_id or reference.endswith(":" + wanted):
            return reference or f"project:{actor_id}", actor_id
    raise RuntimeExecutionError("runtime.actor.unknown", f"responsible actor {requested!r} does not exist in Core")


def snapshot_for_decision(workspace: Any, decision: Any, actor_reference: str) -> CoreSnapshot:
    swarm = workspace.show_swarm(decision.swarm)
    actors = frozenset(
        str(getattr(actor, "reference", "") or f"project:{getattr(actor, 'id', '')}")
        for actor in workspace.list_actors()
    )
    return CoreSnapshot(
        swarm=decision.swarm,
        work=decision.work,
        revision=workspace.work_inspection_read_set_sha256(decision.swarm, decision.work),
        state=decision.state,
        target=decision.target,
        role=decision.role,
        assignments=dict(swarm.assignments),
        actors=actors,
        human_boundary=bool(decision.missing_approvals),
    )


def _availability(root: Path) -> dict[str, RuntimeDiscovery]:
    return {item.id: item for item in discover_runtimes(root)}


def build_governed_runtime_plan(
    root: Path,
    *,
    decision: Any,
    bundle: ExecutionBundle,
    runtime_id: str,
    model: str | None,
    workspace: Any | None = None,
    actor: str | None = None,
    context: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
) -> GovernedRuntimePlan:
    """Build and preflight an exact adapter-backed execution plan."""
    root = root.resolve()
    workspace = workspace or AgoraWorkspace(cwd=root)
    runtime = runtime_for(root, runtime_id)
    binding = binding_for(root, runtime_id, model)
    requirements = requirements_for(bundle, provider=LayaDecisionProvider())
    requested_actor = actor or getattr(decision, "actor", None) or getattr(decision, "role", None)
    actor_reference, actor_id = _actor_reference(workspace, requested_actor)
    snapshot = snapshot_for_decision(workspace, decision, actor_reference)

    envelope = build_envelope(
        snapshot,
        requirements,
        binding,
        bundle,
        actor_id=actor_reference,
        availability=_availability(root),
        candidate=candidate,
        context=context,
    )
    adapter = default_registry(root).get(binding.agent)
    # Fail before creating a Core session if the runtime, envelope or transition is invalid.
    adapter.prepare_execution(envelope.to_dict(), current=(snapshot, requirements))

    target = root / ".agora" / "ai-sdlc" / "execution-envelopes" / bundle.work / f"{bundle.stage or 'step'}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(envelope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    argv = (
        sys.executable,
        "-m",
        "agora_ai_sdlc.adapter_runner",
        "--root",
        str(root),
        "--envelope",
        str(target),
    )
    return GovernedRuntimePlan(
        envelope=envelope,
        requirements=requirements,
        binding=binding,
        runtime=runtime,
        actor_reference=actor_reference,
        actor_id=actor_id,
        runner=shlex.join(argv),
        envelope_path=str(target),
    )
