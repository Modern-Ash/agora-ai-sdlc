"""Provider-neutral semantic progress events for terminal, chat and machine hosts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

SCHEMA = "agora-ai-sdlc/progress-event/v1"
KINDS = {"decision", "routing", "context", "execution", "evidence", "gate", "human-boundary", "result"}
STATUSES = {"started", "progress", "completed", "blocked", "failed"}


@dataclass(frozen=True)
class ProgressEvent:
    sequence: int
    kind: str
    status: str
    stage: str
    message_key: str
    facts: dict[str, Any] = field(default_factory=dict)
    swarm: str | None = None
    work: str | None = None
    revision: int | None = None
    visibility: str = "human"
    at: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("progress.sequence must be positive")
        if self.kind not in KINDS:
            raise ValueError(f"progress.kind invalid: {self.kind}")
        if self.status not in STATUSES:
            raise ValueError(f"progress.status invalid: {self.status}")
        if self.visibility not in {"human", "machine", "both"}:
            raise ValueError(f"progress.visibility invalid: {self.visibility}")

    def snapshot(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema"] = SCHEMA
        data["timestamp"] = self.at or datetime.now(UTC).isoformat()
        data.pop("at", None)
        data["work"] = {
            "swarm": self.swarm,
            "id": self.work,
            "revision": self.revision,
        }
        data.pop("swarm", None)
        data.pop("revision", None)
        return data


def render_chat(event: ProgressEvent) -> str:
    """Durable concise rendering; no spinner/ANSI assumptions."""

    prefix = {
        "started": "…",
        "progress": "…",
        "completed": "✓",
        "blocked": "■",
        "failed": "✗",
    }[event.status]
    detail = str(event.facts.get("summary") or event.message_key)
    return f"{prefix} Agora Flow · {detail}"


def render_tty(event: ProgressEvent, *, spinner: str = "⠋") -> str:
    """TTY rendering may animate externally; event semantics remain stable."""

    if event.status in {"started", "progress"}:
        prefix = spinner
    else:
        prefix = {"completed": "✓", "blocked": "■", "failed": "✗"}[event.status]
    detail = str(event.facts.get("summary") or event.message_key)
    return f"{prefix} Agora Flow · {detail}"


def render_jsonl(event: ProgressEvent) -> str:
    return json.dumps(event.snapshot(), sort_keys=True, separators=(",", ":"))


class ProgressEmitter:
    """Monotonic event factory; emitting has no LLM/runtime side effects."""

    def __init__(self, *, swarm: str | None = None, work: str | None = None, revision: int | None = None):
        self.swarm = swarm
        self.work = work
        self.revision = revision
        self.sequence = 0

    def event(
        self,
        kind: str,
        status: str,
        stage: str,
        message_key: str,
        *,
        facts: dict[str, Any] | None = None,
        visibility: str = "human",
    ) -> ProgressEvent:
        self.sequence += 1
        return ProgressEvent(
            sequence=self.sequence,
            kind=kind,
            status=status,
            stage=stage,
            message_key=message_key,
            facts=dict(facts or {}),
            swarm=self.swarm,
            work=self.work,
            revision=self.revision,
            visibility=visibility,
        )
