"""Reusable conformance checks any concrete RuntimeAdapter must pass."""

from __future__ import annotations

import json
from pathlib import Path

from agora_ai_sdlc.runtime_adapter import (
    AdapterError,
    AdapterRegistry,
    RuntimeAdapter,
    plan_sync,
    sync_projection,
)


def assert_adapter_conformance(adapter: RuntimeAdapter, envelope: dict, root: Path, surfaces=()) -> None:
    registry = AdapterRegistry()
    registry.register(adapter)  # parity with the canonical manifest
    assert registry.get(adapter.integration_id) is adapter

    plan = adapter.plan_projection(tuple(surfaces))
    before = sorted(str(p) for p in root.rglob("*"))
    adapter.describe(root, surfaces=tuple(surfaces), envelope=envelope)
    plan_sync(root, plan)
    sync_projection(root, plan, dry_run=True)
    assert sorted(str(p) for p in root.rglob("*")) == before, "dry-run/describe must not write"

    first = sync_projection(root, plan)
    after_first = {str(p): p.read_text() for p in root.rglob("*") if p.is_file()}
    second = sync_projection(root, plan)
    assert all(action.action == "unchanged" for action in second), "sync must be idempotent"
    assert after_first == {str(p): p.read_text() for p in root.rglob("*") if p.is_file()}
    assert first is not None

    prepared = adapter.prepare_execution(envelope)
    assert prepared.envelope_digest == envelope["digest"]
    assert prepared.operation == envelope["next_transition"]["operation"]
    assert [list(a) for a in prepared.arguments] == [
        [a["name"], a["value"]] for a in envelope["next_transition"]["arguments"]
    ]

    tampered = json.loads(json.dumps(envelope))
    tampered["next_transition"]["operation"] = "lifecycle.transition"
    try:
        adapter.prepare_execution(tampered)
    except Exception as error:  # noqa: BLE001 - any typed rejection is acceptable
        assert getattr(error, "code", "").startswith("envelope."), error
    else:
        raise AssertionError("adapter accepted a tampered envelope")
    assert AdapterError  # imported for adapter authors
