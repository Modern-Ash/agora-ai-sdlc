"""Human-friendly AI-SDLC projection over Agora Core operational state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.depth_profiles import asset_root

_BLOCKER_LIST = re.compile(r"(?P<name>[a-z-]+)=\[(?P<items>[^\]]*)\]")


@dataclass(frozen=True)
class GuidedDecision:
    swarm: str
    work: str
    actor: str | None
    role: str | None
    state: str | None
    target: str | None
    blockers: tuple[str, ...]
    messages: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)


def skill_path() -> Path:
    """Return the packaged portable agent skill."""

    return asset_root("skills") / "agora-ai-sdlc-guided" / "SKILL.md"


def _parse_blocker(blocker: str) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for match in _BLOCKER_LIST.finditer(blocker):
        raw = match.group("items").strip()
        parsed[match.group("name")] = [item.strip() for item in raw.split(",") if item.strip()]
    return parsed


def _humanize(blockers: tuple[str, ...]) -> tuple[str, ...]:
    messages: list[str] = []
    for blocker in blockers:
        details = _parse_blocker(blocker)
        artifacts = details.get("missing-artifacts", [])
        approvals = details.get("missing-approvals", [])
        clarifications = details.get("clarifications", [])
        evidence = details.get("missing-evidence-types", [])

        if artifacts:
            messages.append("Prepare the required project evidence: " + ", ".join(artifacts) + ".")
        if clarifications:
            messages.append("Check whether any material clarification remains before proceeding.")
        if approvals:
            messages.append("Ask the responsible human to approve: " + ", ".join(approvals) + ".")
        if evidence:
            messages.append("Collect the required verification evidence: " + ", ".join(evidence) + ".")
        if not any((artifacts, approvals, clarifications, evidence)):
            messages.append("Agora Core reported a governed blocker; inspect details before continuing.")

    return tuple(dict.fromkeys(messages))


def inspect_next(
    root: Path,
    *,
    swarm: str | None = None,
    work: str | None = None,
) -> GuidedDecision | None:
    """Project the next Core action without mutating lifecycle state."""

    workspace = AgoraWorkspace(cwd=root)
    tasks = workspace.next_actions(swarm_id=swarm, human_only=False, limit=1000)
    if work is not None:
        tasks = [item for item in tasks if item.work_id == work]
    if not tasks:
        return None

    task = tasks[0]
    blockers = tuple(task.blockers)
    return GuidedDecision(
        swarm=str(task.swarm_id or ""),
        work=str(task.work_id or ""),
        actor=task.actor,
        role=task.role,
        state=task.state,
        target=(task.target_states[0] if task.target_states else None),
        blockers=blockers,
        messages=_humanize(blockers),
    )


def render(decision: GuidedDecision | None, *, expert: bool = False) -> str:
    if decision is None:
        return "Agora AI-SDLC\n\nNo governed action currently needs attention."

    lines = [
        "Agora AI-SDLC",
        "",
        f"Work: {decision.swarm}/{decision.work}",
        f"Current stage: {decision.state or 'unknown'}",
    ]
    if decision.target:
        lines.append(f"Next stage: {decision.target}")
    if decision.role:
        owner = f"{decision.role}"
        if decision.actor:
            owner += f" ({decision.actor})"
        lines.append(f"Responsible: {owner}")

    if decision.blocked:
        lines.extend(["", "Before we can continue:"])
        for index, message in enumerate(decision.messages, start=1):
            lines.append(f"  {index}. {message}")
        lines.extend(
            [
                "",
                "The selected AI agent can prepare the non-authoritative work using the installed AI-SDLC skill.",
                "Human approvals remain explicit and are never delegated silently.",
            ]
        )
    else:
        lines.extend(["", "This governed step is ready to continue."])

    if expert:
        lines.extend(["", "Governance details:"])
        lines.extend(f"  - {blocker}" for blocker in decision.blockers)

    return "\n".join(lines)
