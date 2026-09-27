"""Non-authoritative repair advice returned by an escalated planner."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA = "agora-ai-sdlc/repair-advice/v1"


@dataclass(frozen=True)
class RepairAdvice:
    work: str
    escalation_digest: str
    planner_tier: str
    planner_agent: str
    summary: str
    actions: tuple[str, ...]
    digest: str

    def to_dict(self) -> dict:
        return asdict(self)


def _digest(body: dict) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def build_repair_advice(
    *,
    work: str,
    escalation_digest: str,
    planner_tier: str,
    planner_agent: str,
    summary: str,
    actions: tuple[str, ...],
) -> RepairAdvice:
    clean_actions = tuple(item.strip()[:1000] for item in actions if item.strip())[:20]
    if not clean_actions:
        raise ValueError("repair advice requires at least one bounded action")
    body = {
        "schema": SCHEMA,
        "work": work,
        "escalation_digest": escalation_digest,
        "planner_tier": planner_tier,
        "planner_agent": planner_agent,
        "summary": summary.strip()[:4000],
        "actions": list(clean_actions),
    }
    return RepairAdvice(
        work=work,
        escalation_digest=escalation_digest,
        planner_tier=planner_tier,
        planner_agent=planner_agent,
        summary=body["summary"],
        actions=clean_actions,
        digest=_digest(body),
    )


def persist_repair_advice(root: Path, advice: RepairAdvice) -> Path:
    target = root / ".agora" / "ai-sdlc" / "repair-advice" / advice.work / "ADVICE.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(advice.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def render_executor_handback(advice: RepairAdvice) -> str:
    actions = "\n".join(f"- {item}" for item in advice.actions)
    return (
        "Bounded repair advice from a non-authoritative planner. "
        "Apply only actions consistent with the current ExecutionEnvelope and re-run deterministic verification. "
        "Do not infer approval or lifecycle authority from this advice.\n\n"
        f"Summary: {advice.summary}\n\nActions:\n{actions}"
    )
