"""Canonical, immutable agent capability manifests (static integration facts only)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType

from agora_ai_sdlc.runtime_domain import AgentRuntimeRef

MANIFEST_SCHEMA = "agora-ai-sdlc/agent-capability-manifest/v1"
CAPABILITY_IDS = (
    "workspace.read",
    "workspace.write",
    "shell.execute",
    "git.read",
    "git.write",
    "skills",
    "mcp",
    "system_prompt",
    "subagents",
    "model_selection",
    "structured_output",
    "non_interactive",
    "isolated_reviewer",
)


class CapabilityError(ValueError):
    """Unknown agent or capability id; the registry fails closed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

    def diagnostic(self) -> dict:
        return {"code": self.code, "message": str(self)}


@dataclass(frozen=True)
class AgentCapabilityManifest:
    agent: str
    integration: str
    capabilities: MappingProxyType

    def supports(self, capability: str) -> bool:
        if capability not in CAPABILITY_IDS:
            raise CapabilityError("capability.unknown", f"unknown capability id: {capability!r}")
        return self.capabilities[capability]

    def to_dict(self) -> dict:
        return {
            "schema": MANIFEST_SCHEMA,
            "agent": self.agent,
            "integration": self.integration,
            "capabilities": {name: self.capabilities[name] for name in CAPABILITY_IDS},
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def build_manifest(agent: str, integration: str, claimed: dict[str, bool]) -> AgentCapabilityManifest:
    """Validate a claim set: every id is explicit, boolean and known. Nothing is inferred."""
    unknown = sorted(set(claimed) - set(CAPABILITY_IDS))
    if unknown:
        raise CapabilityError("capability.unknown", f"unknown capability ids: {', '.join(unknown)}")
    missing = [name for name in CAPABILITY_IDS if name not in claimed]
    if missing:
        raise CapabilityError("capability.unclaimed", f"capabilities must be explicit, missing: {', '.join(missing)}")
    if any(not isinstance(value, bool) for value in claimed.values()):
        raise CapabilityError("capability.not_boolean", "capability claims must be booleans")
    if not agent.strip() or not integration.strip():
        raise CapabilityError("manifest.identity", "manifest requires agent and integration")
    return AgentCapabilityManifest(agent, integration, MappingProxyType(dict(claimed)))


_BASE = {
    "workspace.read": True,
    "workspace.write": True,
    "shell.execute": True,
    "git.read": True,
    "git.write": True,
    # Reviewer isolation is a session boundary an adapter must provide; no runtime claims it yet.
    "isolated_reviewer": False,
}


def _claims(**overrides: bool) -> dict[str, bool]:
    claims = {name: False for name in CAPABILITY_IDS}
    claims.update(_BASE)
    for key, value in overrides.items():
        claims[key.replace("__", ".")] = value
    return claims


_MANIFESTS = (
    build_manifest(
        "claude",
        "claude-code",
        _claims(
            skills=True,
            mcp=True,
            system_prompt=True,
            subagents=True,
            model_selection=True,
            structured_output=True,
            non_interactive=True,
        ),
    ),
    build_manifest(
        "codex",
        "codex",
        _claims(
            skills=True,
            mcp=True,
            system_prompt=True,
            subagents=False,
            model_selection=True,
            structured_output=True,
            non_interactive=True,
        ),
    ),
    build_manifest(
        "opencode",
        "opencode",
        _claims(
            skills=False,
            mcp=True,
            system_prompt=True,
            subagents=True,
            model_selection=True,
            structured_output=False,
            non_interactive=True,
        ),
    ),
)
_REGISTRY = MappingProxyType({manifest.agent: manifest for manifest in _MANIFESTS})
_INTEGRATION_ALIASES = MappingProxyType({"claude": "claude-code"})


def registered_manifests() -> tuple[AgentCapabilityManifest, ...]:
    return tuple(sorted(_REGISTRY.values(), key=lambda item: item.agent))


def manifest_for(agent: AgentRuntimeRef | str) -> AgentCapabilityManifest:
    """Lookup by agent id (or AgentRuntimeRef); unknown agents fail closed, never default."""
    agent_id = agent.id if isinstance(agent, AgentRuntimeRef) else agent
    manifest = _REGISTRY.get(agent_id.casefold())
    if manifest is None:
        raise CapabilityError("agent.unknown", f"no capability manifest registered for agent {agent_id!r}")
    if isinstance(agent, AgentRuntimeRef):
        declared = _INTEGRATION_ALIASES.get(agent.integration.casefold(), agent.integration.casefold())
        if declared not in {manifest.integration, manifest.agent, "generic"}:
            raise CapabilityError(
                "agent.integration_mismatch",
                f"agent {agent.id!r} integration {agent.integration!r} does not match {manifest.integration!r}",
            )
    return manifest
