"""Provider-neutral RuntimeAdapter SPI: transports and native projections, never decisions.

Adapters translate a validated ExecutionEnvelope into a native invocation and manage
runtime-owned configuration. They do not choose Work, transitions, approvals or fallbacks.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agora_ai_sdlc.agent_capabilities import (
    AgentCapabilityManifest,
    CapabilityError,
    manifest_for,
)
from agora_ai_sdlc.execution_envelope import CoreSnapshot, ExecutionEnvelope, validate_current, verify_integrity
from agora_ai_sdlc.execution_requirements import ExecutionRequirements
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef

SURFACES = ("instructions", "system_prompt", "skills", "mcp", "model_selection", "subagents", "reviewer")
_SURFACE_CAPABILITY = {
    "system_prompt": "system_prompt",
    "skills": "skills",
    "mcp": "mcp",
    "model_selection": "model_selection",
    "subagents": "subagents",
    "reviewer": "isolated_reviewer",
}
BLOCK_BEGIN = "<!-- agora-ai-sdlc:managed:{id}:begin -->"
BLOCK_END = "<!-- agora-ai-sdlc:managed:{id}:end -->"
_SECRET = re.compile(
    r"(?i)(sk-[a-z0-9_-]{8,}|ghp_[a-z0-9]{10,}|bearer\s+[a-z0-9._-]{10,}|"
    r"(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


class AdapterError(ValueError):
    """Typed adapter failure with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {sanitize(message)}")
        self.code = code


_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
Probe = Callable[[list[str]], tuple[int, str]]


def subprocess_probe(command: list[str]) -> tuple[int, str]:
    """Credential-free, bounded version probe."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, error.__class__.__name__
    return result.returncode, (result.stdout or result.stderr or "").strip()


def probe_health(executable: str | None, probe: Probe, minimum: tuple[int, int, int]) -> Health:
    """Installed / responsive / supported-version diagnosis shared by adapters."""
    if not executable:
        return Health(False, False, "executable-not-found")
    code, output = probe([executable, "--version"])
    if code != 0:
        return Health(True, False, f"version-probe-failed:exit-{code}")
    match = _VERSION.search(output)
    if not match:
        return Health(True, False, "version-unparseable")
    version = tuple(int(part) for part in match.groups())
    if version < minimum:
        return Health(True, False, f"unsupported-version:{'.'.join(map(str, version))}")
    return Health(True, True, output.splitlines()[0])


def sanitize(text: str) -> str:
    """Diagnostics never carry secret-looking values."""
    return _SECRET.sub("[redacted]", text)


@dataclass(frozen=True)
class ProjectionEntry:
    """One managed native artifact: a marked text block or a set of top-level JSON keys."""

    path: str
    kind: str  # "text_block" | "json_keys"
    surface: str
    content: str | None = None
    keys: Mapping[str, Any] | None = None
    block_id: str = "main"


@dataclass(frozen=True)
class ProjectionPlan:
    adapter: str
    entries: tuple[ProjectionEntry, ...]
    unsupported_surfaces: tuple[str, ...] = ()

    def managed(self) -> list[dict]:
        return [
            {"path": e.path, "kind": e.kind, "keys": sorted(e.keys) if e.keys else None, "block": e.block_id}
            for e in self.entries
        ]


@dataclass(frozen=True)
class SyncAction:
    path: str
    action: str  # create | update | unchanged
    backup: str | None = None


@dataclass(frozen=True)
class PreparedExecution:
    adapter: str
    envelope_digest: str
    operation: str
    arguments: tuple[tuple[str, str], ...]
    argv: tuple[str, ...]
    stdin: str
    model: str | None = None


@dataclass(frozen=True)
class ExecutionOutcome:
    """Raw transport result only; it grants no acceptance, approval or lifecycle change."""

    exit_code: int
    output: str
    structured: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class Health:
    installed: bool
    responsive: bool
    detail: str | None = None


Runner = Callable[[tuple[str, ...], str], tuple[int, str]]


class RuntimeAdapter(ABC):
    """Base class: fixed template methods, provider-specific hooks kept narrow."""

    integration_id: str

    @property
    def advertised_capabilities(self) -> frozenset[str]:
        """Claims must equal the canonical manifest; the registry enforces parity."""
        return frozenset(name for name, ok in self.capability_manifest().capabilities.items() if ok)

    def capability_manifest(self) -> AgentCapabilityManifest:
        return manifest_for(self.integration_id)

    @abstractmethod
    def health(self) -> Health: ...

    @abstractmethod
    def plan_projection(self, surfaces: tuple[str, ...]) -> ProjectionPlan:
        """Deterministic projection of canonical Agora assets for the requested surfaces."""

    @abstractmethod
    def render_invocation(self, envelope: ExecutionEnvelope) -> PreparedExecution:
        """Native prompt/argv for the envelope; transport only."""

    def parse_output(self, exit_code: int, output: str) -> ExecutionOutcome:
        return ExecutionOutcome(exit_code=exit_code, output=sanitize(output))

    # -- template methods -------------------------------------------------------------------
    def prepare_execution(
        self,
        payload: Mapping[str, Any],
        *,
        current: tuple[CoreSnapshot, ExecutionRequirements] | None = None,
    ) -> PreparedExecution:
        """Verify, optionally revalidate against current Core state, then render the invocation."""
        envelope = verify_integrity(payload)
        if current is not None:
            check = validate_current(envelope, *current)
            if not check.valid:
                raise AdapterError("adapter.stale_envelope", ",".join(check.reasons))
        if not envelope.executable or envelope.binding is None:
            raise AdapterError("adapter.not_executable", "envelope is a stop/human-authority envelope")
        try:
            declared = manifest_for(envelope.binding.agent).agent
        except CapabilityError as error:
            raise AdapterError("adapter.agent_unknown", str(error)) from error
        if declared != self.capability_manifest().agent:
            raise AdapterError(
                "adapter.agent_mismatch", f"envelope targets {declared!r}, adapter is {self.integration_id!r}"
            )
        prepared = self.render_invocation(envelope)
        if (prepared.envelope_digest, prepared.operation, prepared.arguments) != (
            payload["digest"],
            envelope.operation,
            envelope.arguments,
        ):
            raise AdapterError("adapter.transition_altered", "adapter changed the envelope transition or identity")
        return prepared

    def launch(self, prepared: PreparedExecution, runner: Runner) -> ExecutionOutcome:
        exit_code, output = runner(prepared.argv, prepared.stdin)
        return self.parse_output(exit_code, output)

    def describe(
        self, root: Path, *, surfaces: tuple[str, ...] = (), envelope: Mapping[str, Any] | None = None
    ) -> dict:
        """Read-only diagnostics; performs no writes and exposes no secrets."""
        manifest = self.capability_manifest()
        plan = self.plan_projection(surfaces)
        health = self.health()
        binding = None
        if envelope is not None:
            runtime = verify_integrity(envelope).binding
            binding = None if runtime is None else runtime.to_dict()
        return {
            "adapter": self.integration_id,
            "capabilities": manifest.to_dict()["capabilities"],
            "manifest_digest": manifest.digest,
            "managed": plan.managed(),
            "sync": [action.__dict__ for action in plan_sync(root, plan)],
            "unsupported_surfaces": list(plan.unsupported_surfaces),
            "model_binding": binding,
            "health": {
                "installed": health.installed,
                "responsive": health.responsive,
                "detail": sanitize(health.detail or ""),
            },
        }


def supported_surfaces(
    manifest: AgentCapabilityManifest, requested: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split requested surfaces by canonical capability; unknown surfaces fail closed."""
    unknown = sorted(set(requested) - set(SURFACES))
    if unknown:
        raise AdapterError("projection.unknown_surface", f"unknown projection surfaces: {unknown}")
    ok, missing = [], []
    for surface in requested:
        capability = _SURFACE_CAPABILITY.get(surface)
        (ok if capability is None or manifest.supports(capability) else missing).append(surface)
    return tuple(ok), tuple(missing)


# -- registry -----------------------------------------------------------------------------------
class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, RuntimeAdapter] = {}

    def register(self, adapter: RuntimeAdapter) -> None:
        try:
            manifest = adapter.capability_manifest()
        except CapabilityError as error:
            raise AdapterError("adapter.no_manifest", str(error)) from error
        canonical = frozenset(name for name, ok in manifest.capabilities.items() if ok)
        if adapter.advertised_capabilities != canonical:
            raise AdapterError(
                "adapter.capability_parity", f"{manifest.agent}: advertised capabilities differ from manifest"
            )
        if manifest.agent in self._adapters:
            raise AdapterError("adapter.duplicate", f"adapter already registered for {manifest.agent!r}")
        self._adapters[manifest.agent] = adapter

    def get(self, agent: AgentRuntimeRef | str) -> RuntimeAdapter:
        try:
            key = manifest_for(agent).agent
        except CapabilityError as error:
            raise AdapterError("adapter.unknown", str(error)) from error
        adapter = self._adapters.get(key)
        if adapter is None:
            raise AdapterError("adapter.missing", f"no adapter registered for {key!r}")
        return adapter

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


# -- managed projection -------------------------------------------------------------------------
def _target(root: Path, entry: ProjectionEntry) -> Path:
    relative = Path(entry.path)
    if relative.is_absolute() or ".." in relative.parts or not entry.path.strip():
        raise AdapterError("projection.path", f"projection path must stay inside the workspace: {entry.path!r}")
    return root / relative


def _managed_text(entry: ProjectionEntry) -> str:
    if entry.content is None or _SECRET.search(entry.content):
        raise AdapterError("projection.content", "projection content is missing or contains secret-looking values")
    begin, end = BLOCK_BEGIN.format(id=entry.block_id), BLOCK_END.format(id=entry.block_id)
    return f"{begin}\n{entry.content.rstrip()}\n{end}"


def _merge_text(existing: str, entry: ProjectionEntry) -> str:
    block = _managed_text(entry)
    begin, end = BLOCK_BEGIN.format(id=entry.block_id), BLOCK_END.format(id=entry.block_id)
    if begin in existing and end in existing:
        head, rest = existing.split(begin, 1)
        _, tail = rest.split(end, 1)
        return head + block + tail
    separator = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + separator + block + "\n"


def _merge_json(existing: str, entry: ProjectionEntry) -> str:
    if not entry.keys or _SECRET.search(json.dumps(entry.keys)):
        raise AdapterError("projection.content", "projection keys are missing or contain secret-looking values")
    try:
        data = json.loads(existing) if existing.strip() else {}
    except json.JSONDecodeError as error:
        raise AdapterError(
            "projection.unparseable", f"{entry.path} is not valid JSON; refusing to overwrite"
        ) from error
    if not isinstance(data, dict):
        raise AdapterError("projection.unparseable", f"{entry.path} is not a JSON object; refusing to overwrite")
    data.update({key: entry.keys[key] for key in sorted(entry.keys)})
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _desired(root: Path, entry: ProjectionEntry) -> tuple[Path, str | None, str]:
    path = _target(root, entry)
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    if entry.kind == "text_block":
        merged = _merge_text(existing or "", entry)
    elif entry.kind == "json_keys":
        merged = _merge_json(existing or "", entry)
    else:
        raise AdapterError("projection.kind", f"unknown projection kind {entry.kind!r}")
    return path, existing, merged


def plan_sync(root: Path, plan: ProjectionPlan) -> tuple[SyncAction, ...]:
    """Dry-run: what a sync would do. Performs no writes."""
    actions = []
    for entry in plan.entries:
        _, existing, merged = _desired(root, entry)
        action = "create" if existing is None else ("unchanged" if existing == merged else "update")
        actions.append(SyncAction(entry.path, action))
    return tuple(actions)


def sync_projection(root: Path, plan: ProjectionPlan, *, dry_run: bool = False) -> tuple[SyncAction, ...]:
    """Apply managed projection; unmanaged content survives, replaced files are backed up first."""
    if dry_run:
        return plan_sync(root, plan)
    results = []
    for entry in plan.entries:
        path, existing, merged = _desired(root, entry)
        if existing == merged:
            results.append(SyncAction(entry.path, "unchanged"))
            continue
        backup = None
        if existing is not None:
            digest = hashlib.sha256(existing.encode()).hexdigest()[:12]
            backup_path = (
                root / ".agora" / "ai-sdlc" / "backups" / plan.adapter / f"{entry.path.replace('/', '__')}.{digest}.bak"
            )
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(existing, encoding="utf-8")
            backup = str(backup_path.relative_to(root))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(merged, encoding="utf-8")
        results.append(SyncAction(entry.path, "create" if existing is None else "update", backup))
    return tuple(results)


__all__ = [
    "AdapterError",
    "AdapterRegistry",
    "ExecutionOutcome",
    "Health",
    "PreparedExecution",
    "ProjectionEntry",
    "ProjectionPlan",
    "RuntimeAdapter",
    "SyncAction",
    "plan_sync",
    "probe_health",
    "sanitize",
    "subprocess_probe",
    "supported_surfaces",
    "sync_projection",
]
