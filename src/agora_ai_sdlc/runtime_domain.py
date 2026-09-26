"""Provider-neutral runtime taxonomy: agent runtimes are distinct from model runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

BINDING_SCHEMA = "agora-ai-sdlc/runtime-binding/v2"

# Agent hosts are repository-aware executors; model runtimes only serve models.
AGENT_HOSTS = {"claude": "claude-code", "codex": "codex", "opencode": "opencode"}
MODEL_RUNTIMES = ("ollama",)
_INTEGRATION_ALIASES = {"claude-code": "claude"}


class RuntimeKind(str, Enum):
    AGENT = "agent"
    MODEL = "model"


class RuntimeNormalizationError(ValueError):
    """A legacy runtime entry cannot be safely normalized; never guessed."""

    def __init__(self, code: str, message: str, *, runtime_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.runtime_id = runtime_id

    def diagnostic(self) -> dict:
        return {"code": self.code, "message": str(self), "runtime_id": self.runtime_id}


@dataclass(frozen=True)
class AgentRuntimeRef:
    id: str
    integration: str


@dataclass(frozen=True)
class ModelRuntimeRef:
    id: str
    provider: str
    model: str


@dataclass(frozen=True)
class RuntimeBinding:
    agent: AgentRuntimeRef
    model: ModelRuntimeRef | None = None

    def to_dict(self) -> dict:
        return {
            "schema": BINDING_SCHEMA,
            "agent": {"id": self.agent.id, "integration": self.agent.integration},
            "model": None
            if self.model is None
            else {"id": self.model.id, "provider": self.model.provider, "model": self.model.model},
        }

    def to_legacy(self) -> dict[str, str]:
        """Flat v1 shape, kept for consumers that predate the taxonomy."""
        return {
            "id": self.agent.id,
            "integration": self.agent.integration,
            "provider": self.model.provider if self.model else "",
            "model": self.model.model if self.model else "",
        }


def runtime_kind(runtime_id: str) -> RuntimeKind:
    """Kind of a well-known runtime id; unknown ids are agent hosts by configuration."""
    return RuntimeKind.MODEL if runtime_id.casefold() in MODEL_RUNTIMES else RuntimeKind.AGENT


def _text(entry: Mapping, key: str) -> str:
    value = entry.get(key)
    return value.strip() if isinstance(value, str) else ""


def normalize_runtime(entry: Mapping) -> RuntimeBinding:
    """Deterministically map a v1 flat entry or a v2 binding mapping to a RuntimeBinding."""
    if not isinstance(entry, Mapping):
        raise RuntimeNormalizationError("runtime.not_a_mapping", "runtime entry must be a mapping")
    if isinstance(entry.get("agent"), Mapping):
        return _from_v2(entry)

    runtime_id = _text(entry, "id")
    integration = _text(entry, "integration")
    provider = _text(entry, "provider")
    model = _text(entry, "model")
    if not runtime_id:
        raise RuntimeNormalizationError("runtime.legacy_missing_id", "legacy runtime entry requires an id")
    if not integration:
        raise RuntimeNormalizationError(
            "runtime.legacy_missing_integration",
            f"legacy runtime {runtime_id!r} requires an integration",
            runtime_id=runtime_id,
        )
    canonical_integration = _INTEGRATION_ALIASES.get(integration.casefold(), integration.casefold())
    if runtime_id.casefold() in MODEL_RUNTIMES or canonical_integration in MODEL_RUNTIMES:
        raise RuntimeNormalizationError(
            "runtime.legacy_model_runtime_as_agent",
            f"legacy runtime {runtime_id!r} names a model runtime as an agent host; "
            "declare an agent runtime (for example opencode) with this runtime as its model",
            runtime_id=runtime_id,
        )
    if bool(provider) != bool(model):
        raise RuntimeNormalizationError(
            "runtime.legacy_partial_model",
            f"legacy runtime {runtime_id!r} must set both provider and model or neither",
            runtime_id=runtime_id,
        )
    agent = AgentRuntimeRef(id=runtime_id, integration=integration)
    if not provider:
        return RuntimeBinding(agent=agent, model=None)
    model_id = provider if provider.casefold() in MODEL_RUNTIMES else agent.id
    return RuntimeBinding(agent=agent, model=ModelRuntimeRef(id=model_id, provider=provider, model=model))


def _from_v2(entry: Mapping) -> RuntimeBinding:
    agent_entry = entry["agent"]
    agent_id = _text(agent_entry, "id")
    integration = _text(agent_entry, "integration")
    if not agent_id or not integration:
        raise RuntimeNormalizationError("runtime.agent_incomplete", "agent runtime requires id and integration")
    if agent_id.casefold() in MODEL_RUNTIMES:
        raise RuntimeNormalizationError(
            "runtime.model_runtime_as_agent",
            f"{agent_id!r} is a model runtime and cannot satisfy an agent-execution requirement",
            runtime_id=agent_id,
        )
    model_entry = entry.get("model")
    if model_entry is None:
        return RuntimeBinding(agent=AgentRuntimeRef(agent_id, integration))
    if not isinstance(model_entry, Mapping):
        raise RuntimeNormalizationError("runtime.model_invalid", "model runtime must be a mapping or null")
    provider = _text(model_entry, "provider")
    model = _text(model_entry, "model")
    if not provider or not model:
        raise RuntimeNormalizationError("runtime.model_incomplete", "model runtime requires provider and model")
    return RuntimeBinding(
        agent=AgentRuntimeRef(agent_id, integration),
        model=ModelRuntimeRef(id=_text(model_entry, "id") or provider, provider=provider, model=model),
    )
