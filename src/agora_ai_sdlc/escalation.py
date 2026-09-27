"""Bounded, durable escalation packages for cost-aware execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.execution_requirements import ExecutionRequirements
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_domain import RuntimeBinding
from agora_ai_sdlc.runtime_pool import PoolSelection, select_from_runtime_pool

SCHEMA = "agora-ai-sdlc/escalation-package/v1"


@dataclass(frozen=True)
class EscalationPackage:
    swarm: str
    work: str
    activity_class: str
    failed_tier: str
    failed_binding: dict
    attempts: int
    diagnostic: str
    changed_paths: tuple[str, ...]
    verification_commands: tuple[str, ...]
    objective: str
    question: str
    digest: str

    def to_dict(self) -> dict:
        return asdict(self)


def _digest(body: dict) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def build_escalation_package(
    *,
    swarm: str,
    work: str,
    requirements: ExecutionRequirements,
    failed_tier: str,
    failed_binding: RuntimeBinding,
    attempts: int,
    diagnostic: str,
    changed_paths: tuple[str, ...] = (),
    verification_commands: tuple[str, ...] = (),
    objective: str = "",
    question: str = "Diagnose the blocker and return a bounded repair plan for the cheap executor.",
) -> EscalationPackage:
    if attempts < 1:
        raise ValueError("escalation attempts must be positive")
    body = {
        "schema": SCHEMA,
        "swarm": swarm,
        "work": work,
        "activity_class": requirements.activity_class,
        "failed_tier": failed_tier,
        "failed_binding": failed_binding.to_dict(),
        "attempts": attempts,
        "diagnostic": diagnostic.strip()[:6000],
        "changed_paths": list(changed_paths[:100]),
        "verification_commands": list(verification_commands[:20]),
        "objective": objective.strip()[:2000],
        "question": question.strip()[:1000],
    }
    return EscalationPackage(
        swarm=swarm,
        work=work,
        activity_class=requirements.activity_class,
        failed_tier=failed_tier,
        failed_binding=failed_binding.to_dict(),
        attempts=attempts,
        diagnostic=body["diagnostic"],
        changed_paths=tuple(body["changed_paths"]),
        verification_commands=tuple(body["verification_commands"]),
        objective=body["objective"],
        question=body["question"],
        digest=_digest(body),
    )


def persist_escalation_package(root: Path, package: EscalationPackage) -> Path:
    target = root / ".agora" / "ai-sdlc" / "escalations" / package.work / f"attempt-{package.attempts}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(package.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def recommend_escalation(
    root: Path,
    requirements: ExecutionRequirements,
    *,
    failed_tier: str,
    availability: dict[str, RuntimeDiscovery] | None = None,
    work: str | None = None,
) -> PoolSelection | None:
    """Recommend, but never launch, the next authorized more expensive tier."""

    return select_from_runtime_pool(
        root,
        requirements,
        availability=availability,
        minimum_tier_exclusive=failed_tier,
        purpose="planner",
        work=work,
    )
