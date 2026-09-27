"""Durable economic telemetry for cost-aware runtime routing."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "agora-ai-sdlc/economic-event/v1"


def record_economic_event(
    root: Path,
    *,
    work: str,
    kind: str,
    tier: str | None,
    agent: str | None,
    model: str | None,
    fields: dict[str, Any] | None = None,
) -> Path:
    target = root / ".agora" / "ai-sdlc" / "economics" / work / "events.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "kind": kind,
        "tier": tier,
        "agent": agent,
        "model": model,
        **dict(sorted((fields or {}).items())),
    }
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    return target


def summarize_economics(root: Path, work: str) -> dict[str, Any]:
    path = root / ".agora" / "ai-sdlc" / "economics" / work / "events.jsonl"
    if not path.is_file():
        return {"work": work, "events": 0, "tiers": {}, "kinds": {}, "paid_events": 0, "frontier_events": 0}
    tiers: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    total = 0
    paid = 0
    frontier = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        tier = event.get("tier")
        kind = event.get("kind")
        if isinstance(tier, str):
            tiers[tier] += 1
            if tier.startswith("paid-") or tier == "frontier":
                paid += 1
            if tier == "frontier":
                frontier += 1
        if isinstance(kind, str):
            kinds[kind] += 1
    return {
        "work": work,
        "events": total,
        "tiers": dict(sorted(tiers.items())),
        "kinds": dict(sorted(kinds.items())),
        "paid_events": paid,
        "frontier_events": frontier,
    }
