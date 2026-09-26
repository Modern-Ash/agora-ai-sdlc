"""Read-only runtime diagnostics and preview-only migration to runtime-binding/v2."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import yaml
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.agent_capabilities import CapabilityError, manifest_for
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.runtime_adapter import AdapterError, plan_sync, sanitize
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes
from agora_ai_sdlc.runtime_domain import RuntimeBinding, RuntimeNormalizationError, normalize_runtime
from agora_ai_sdlc.runtime_selection import admit_binding

MIGRATION_SCHEMA = "agora-ai-sdlc/runtime-migration-preview/v1"
DIAGNOSTICS_SCHEMA = "agora-ai-sdlc/runtime-diagnostics/v1"


def _project_runtimes(root: Path) -> list[Any]:
    metadata = root / "ai-sdlc" / "project.yaml"
    if not metadata.is_file():
        return []
    try:
        payload = yaml.safe_load(metadata.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    runtimes = payload.get("runtimes") if isinstance(payload, dict) else None
    return list(runtimes) if isinstance(runtimes, list) else []


def _actor_entries(root: Path) -> list[dict]:
    """Legacy runtime metadata readable from Core actors; the actor id is never used as a runtime id."""
    try:
        actors = AgoraWorkspace(cwd=root).list_actors()
    except (OSError, ValueError):
        return []
    entries = []
    for actor in actors:
        if getattr(actor, "kind", None) != "ai-agent":
            continue
        entries.append(
            {
                "actor": str(getattr(actor, "reference", getattr(actor, "id", ""))),
                "integration": str(getattr(actor, "integration", "") or ""),
                "provider": str(getattr(actor, "provider", "") or ""),
                "model": str(getattr(actor, "model", "") or ""),
            }
        )
    return entries


def _migrate(entry: Any, *, source: str, label: str) -> dict:
    record: dict[str, Any] = {"source": source, "from": entry, "label": label}
    try:
        record["to"] = normalize_runtime(entry).to_dict()
    except RuntimeNormalizationError as error:
        record["diagnostic"] = error.diagnostic()
    return record


def preview_migration(root: Path) -> dict:
    """Deterministic preview of the v2 representation. Never writes; ambiguous entries get a typed diagnostic."""
    records = [
        _migrate(
            entry, source="ai-sdlc/project.yaml", label=str(entry.get("id", "?")) if isinstance(entry, dict) else "?"
        )
        for entry in _project_runtimes(root)
    ]
    for actor in _actor_entries(root):
        legacy = {
            "id": actor["integration"],
            "integration": actor["integration"],
            "provider": actor["provider"],
            "model": actor["model"],
        }
        records.append(_migrate(legacy, source="core-actor", label=actor["actor"]))
    return {
        "schema": MIGRATION_SCHEMA,
        "writes": False,
        "compatibility": "v1 flat runtime entries stay readable; `selected` keeps the flat v1 fields and adds `binding`",
        "records": records,
        "ambiguous": sum(1 for record in records if "diagnostic" in record),
    }


def diagnose(
    root: Path,
    *,
    availability: Mapping[str, RuntimeDiscovery] | None = None,
    laya_available: Callable[[], bool] | None = None,
    activity: str = "construction.implementation",
) -> dict:
    """Per configured binding: agent, capabilities, model runtime, eligibility, adapter and projection state."""
    found = availability if availability is not None else {item.id: item for item in discover_runtimes(root)}
    requirements = requirements_for_activity(activity)
    registry = default_registry(root)
    runtimes = []
    for record in preview_migration(root)["records"]:
        if "diagnostic" in record:
            runtimes.append({"label": record["label"], "status": "ambiguous", "diagnostic": record["diagnostic"]})
            continue
        binding = normalize_runtime(record["to"])
        runtimes.append(_binding_report(root, binding, found, requirements, registry))
    laya = "unknown"
    if laya_available is not None:
        laya = "available (advisory only)" if laya_available() else "unavailable (deterministic requirements only)"
    return {"schema": DIAGNOSTICS_SCHEMA, "activity": activity, "laya": laya, "runtimes": runtimes}


def _binding_report(root: Path, binding: RuntimeBinding, found: Mapping, requirements, registry) -> dict:
    report: dict[str, Any] = {
        "agent_runtime": binding.agent.id,
        "model_runtime": None if binding.model is None else binding.model.id,
        "model": None if binding.model is None else binding.model.model,
    }
    try:
        manifest = manifest_for(binding.agent)
        report["agent_capabilities"] = [name for name, ok in manifest.capabilities.items() if ok]
    except CapabilityError as error:
        return {**report, "status": "no-manifest", "diagnostic": error.diagnostic()}
    blockers = admit_binding(binding, requirements, found)
    report["binding_status"] = "eligible" if not blockers else "blocked"
    report["blockers"] = [blocker["code"] for blocker in blockers]
    try:
        adapter = registry.get(binding.agent)
    except AdapterError as error:
        report.update(adapter=None, projection="no-adapter", diagnostic=sanitize(str(error)))
        return report
    report["adapter"] = adapter.integration_id
    try:
        actions = plan_sync(root, adapter.plan_projection(()))
        report["projection"] = "in sync" if all(a.action == "unchanged" for a in actions) else "drifted"
    except AdapterError as error:
        report["projection"] = "unreadable"
        report["diagnostic"] = sanitize(str(error))
    return report


def render_diagnostics(report: dict) -> str:
    lines = [f"Laya: {report['laya']}"]
    for item in report["runtimes"]:
        if item.get("status") in ("ambiguous", "no-manifest"):
            lines += [
                "",
                f"Runtime: {item.get('label') or item.get('agent_runtime')} — {item['status']}: {item['diagnostic']['code']}",
            ]
            continue
        lines += [
            "",
            f"Agent runtime: {item['agent_runtime']}",
            f"Agent capabilities: {', '.join(item['agent_capabilities'])}",
            f"Model runtime: {item['model_runtime'] or '-'}",
            f"Model: {item['model'] or '-'}",
            f"Binding status: {item['binding_status']}"
            + (f" ({', '.join(item['blockers'])})" if item["blockers"] else ""),
            f"Adapter: {item.get('adapter') or '-'}",
            f"Projection: {item['projection']}",
        ]
    return "\n".join(lines)
