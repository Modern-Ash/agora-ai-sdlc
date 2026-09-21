"""Human-friendly AI-SDLC projection over Agora Core operational state."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.depth_profiles import asset_root

_BLOCKER_LIST = re.compile(r"(?P<name>[a-z-]+)=\[(?P<items>[^\]]*)\]")


@dataclass(frozen=True)
class GuidedDecision:
    swarm: str
    work: str
    title: str | None
    method: str | None
    actor: str | None
    role: str | None
    state: str | None
    target: str | None
    gate: str | None
    blockers: tuple[str, ...]
    messages: tuple[str, ...]
    missing_artifacts: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    missing_approvals: tuple[str, ...] = ()
    unsatisfied_criteria: tuple[str, ...] = ()
    git_issues: tuple[str, ...] = ()
    clarification_issues: tuple[str, ...] = ()
    ready_for_human_approval: bool = False
    ready_to_transition: bool = False

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    def snapshot(self) -> dict:
        return asdict(self)


def skill_path() -> Path:
    """Return the packaged portable agent skill."""

    return asset_root("skills") / "agora-ai-sdlc-guided" / "SKILL.md"


def _parse_blocker(blocker: str) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for match in _BLOCKER_LIST.finditer(blocker):
        raw = match.group("items").strip()
        parsed[match.group("name")] = [item.strip() for item in raw.split(",") if item.strip()]
    return parsed


def _combined_blocker_details(blockers: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    collected: dict[str, list[str]] = {}
    for blocker in blockers:
        for key, values in _parse_blocker(blocker).items():
            bucket = collected.setdefault(key, [])
            for value in values:
                if value not in bucket:
                    bucket.append(value)
    return {key: tuple(values) for key, values in collected.items()}


def _humanize(
    blockers: tuple[str, ...],
    *,
    missing_artifacts: tuple[str, ...] = (),
    missing_evidence: tuple[str, ...] = (),
    missing_approvals: tuple[str, ...] = (),
    unsatisfied_criteria: tuple[str, ...] = (),
    git_issues: tuple[str, ...] = (),
    clarification_issues: tuple[str, ...] = (),
) -> tuple[str, ...]:
    messages: list[str] = []
    if missing_artifacts:
        messages.append("Prepare the required project evidence: " + ", ".join(missing_artifacts) + ".")
    if unsatisfied_criteria:
        messages.append("Complete the required acceptance criteria: " + ", ".join(unsatisfied_criteria) + ".")
    if clarification_issues:
        messages.append("Resolve the current clarification requirement before proceeding.")
    if missing_evidence:
        messages.append("Collect the required verification evidence: " + ", ".join(missing_evidence) + ".")
    if git_issues:
        messages.append("Resolve the repository policy requirement: " + "; ".join(git_issues) + ".")
    if missing_approvals:
        messages.append("Ask the responsible human to approve: " + ", ".join(missing_approvals) + ".")
    if blockers and not messages:
        messages.append("Agora Core reported a governed blocker; inspect details before continuing.")
    return tuple(messages)


def _transition_details(
    workspace: AgoraWorkspace,
    swarm: str,
    work: str,
    target: str | None,
) -> dict:
    if target is None:
        return {}
    try:
        readiness = workspace.next_gate_readiness(swarm, work)
    except (OSError, ValueError):
        return {}
    transitions = readiness.get("transitions") or []
    return next(
        (item for item in transitions if item.get("target_state") == target),
        transitions[0] if transitions else {},
    )


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
    parsed = _combined_blocker_details(blockers)
    target = task.target_states[0] if task.target_states else None
    details = _transition_details(workspace, str(task.swarm_id or ""), str(task.work_id or ""), target)
    gate = details.get("gate") or {}

    missing_artifacts = tuple(gate.get("missing_artifacts") or parsed.get("missing-artifacts", ()))
    missing_evidence = tuple(gate.get("missing_evidence_types") or parsed.get("missing-evidence-types", ()))
    missing_approvals = tuple(gate.get("missing_approvals") or parsed.get("missing-approvals", ()))
    unsatisfied_criteria = tuple(gate.get("unsatisfied") or parsed.get("unsatisfied", ()))
    git_issues = tuple(gate.get("git_issues") or parsed.get("git", ()))
    clarification_issues = parsed.get("clarifications", ())

    messages = _humanize(
        blockers,
        missing_artifacts=missing_artifacts,
        missing_evidence=missing_evidence,
        missing_approvals=missing_approvals,
        unsatisfied_criteria=unsatisfied_criteria,
        git_issues=git_issues,
        clarification_issues=clarification_issues,
    )
    return GuidedDecision(
        swarm=str(task.swarm_id or ""),
        work=str(task.work_id or ""),
        title=details.get("title"),
        method=details.get("method"),
        actor=task.actor,
        role=task.role,
        state=task.state,
        target=target,
        gate=gate.get("gate"),
        blockers=blockers,
        messages=messages,
        missing_artifacts=missing_artifacts,
        missing_evidence=missing_evidence,
        missing_approvals=missing_approvals,
        unsatisfied_criteria=unsatisfied_criteria,
        git_issues=git_issues,
        clarification_issues=clarification_issues,
        ready_for_human_approval=bool(details.get("ready_for_human_approval", False)),
        ready_to_transition=bool(details.get("ready_to_complete", not blockers)),
    )


def command_plan(decision: GuidedDecision) -> tuple[tuple[str, str], ...]:
    """Build an advisory command bundle. Commands never run from this function."""

    actor = decision.actor or "<responsible-actor>"
    commands: list[tuple[str, str]] = []

    if "readiness-assessment" in decision.missing_artifacts:
        artifact_path = f"docs/governance/{decision.work}-readiness.md"
        commands.append(
            (
                f"prepare {artifact_path}",
                "AI drafts the packaged readiness template; the responsible human reviews it before registration.",
            )
        )
        commands.append(
            (
                (
                    "agora artifact add "
                    f"--swarm {decision.swarm} --work {decision.work} "
                    f"--kind readiness-assessment --uri repo://{artifact_path} --by {actor}"
                ),
                "Register the accepted artifact in Agora Core.",
            )
        )

    if decision.clarification_issues:
        commands.append(
            (
                f"agora work clarify --swarm {decision.swarm} --work {decision.work} --by {actor}",
                "Run the governed clarification step; use an AI executor only as assistance when Core permits it.",
            )
        )

    for approval in decision.missing_approvals:
        commands.append(
            (
                (
                    "agora approval add "
                    f"--swarm {decision.swarm} --work {decision.work} "
                    f"--role {approval} --by {actor} --note \"Reviewed and approved\""
                ),
                "Run only after explicit confirmation from the responsible human.",
            )
        )

    if decision.target:
        commands.append(
            (
                (
                    "agora work transition "
                    f"--swarm {decision.swarm} --work {decision.work} --to {decision.target} --by {actor}"
                ),
                "Attempt only after a fresh Core readiness check reports the gate satisfied.",
            )
        )

    commands.append(
        (
            f"agora-ai-sdlc continue --swarm {decision.swarm} --work {decision.work}",
            "Re-read authoritative state after mutations and present the next human decision.",
        )
    )
    return tuple(commands)


def _status_items(decision: GuidedDecision) -> tuple[tuple[str, bool], ...]:
    return (
        ("Required artifacts", not decision.missing_artifacts),
        ("Acceptance criteria", not decision.unsatisfied_criteria),
        ("Clarifications", not decision.clarification_issues),
        ("Verification evidence", not decision.missing_evidence),
        ("Git/repository policy", not decision.git_issues),
        ("Human approvals", not decision.missing_approvals),
    )


def render(
    decision: GuidedDecision | None,
    *,
    expert: bool = False,
    show_commands: bool = False,
) -> str:
    if decision is None:
        return "Agora AI-SDLC\n\nNo governed action currently needs attention."

    lines = ["Agora AI-SDLC", ""]
    if decision.title:
        lines.append(f"Objective: {decision.title}")
    lines.extend(
        [
            f"Work: {decision.swarm}/{decision.work}",
            f"Method: {decision.method or 'unknown'}",
            f"Stage: {decision.state or 'unknown'}"
            + (f"  ->  {decision.target}" if decision.target else ""),
        ]
    )
    if decision.gate:
        lines.append(f"Decision gate: {decision.gate}")
    if decision.role:
        owner = decision.role
        if decision.actor:
            owner += f" ({decision.actor})"
        lines.append(f"Responsible: {owner}")

    lines.extend(["", "Readiness"])
    for label, satisfied in _status_items(decision):
        marker = "✓" if satisfied else "!"
        lines.append(f"  {marker} {label}")

    if decision.messages:
        lines.extend(["", "What remains"])
        for index, message in enumerate(decision.messages, start=1):
            lines.append(f"  {index}. {message}")

    lines.extend(["", "Responsibility boundary"])
    if decision.actor and decision.role:
        lines.append(f"  Human/assigned authority: {decision.actor} as {decision.role}.")
    lines.append("  AI may inspect, explain, draft artifacts and execute explicitly delegated bounded work.")
    lines.append("  AI may not invent approval, transfer a human role, or bypass a Core gate.")

    if decision.ready_for_human_approval and decision.missing_approvals:
        lines.extend(
            [
                "",
                "Decision needed",
                "  Technical/readiness obligations are satisfied; explicit human approval is now required.",
                "  [A] Approve  [R] Review evidence  [E] Edit proposal  [D] Governance details  [X] Stop",
            ]
        )
    elif decision.blocked:
        lines.extend(
            [
                "",
                "Recommended action",
                "  Let the selected AI agent prepare the non-authoritative items above, then return for human review.",
                "  [P] Prepare with AI  [R] Review context  [D] Governance details  [X] Stop",
            ]
        )
    else:
        lines.extend(["", "Recommended action", "  This governed step is ready for the responsible actor."])

    if show_commands:
        lines.extend(["", "Underlying command bundle"])
        for index, (command, reason) in enumerate(command_plan(decision), start=1):
            lines.append(f"  {index}. {command}")
            lines.append(f"     {reason}")

    if expert:
        lines.extend(["", "Governance details"])
        if decision.blockers:
            lines.extend(f"  - {blocker}" for blocker in decision.blockers)
        else:
            lines.append("  - No Core blockers.")
        lines.append("")
        lines.append("Structured decision")
        lines.append(json.dumps(decision.snapshot(), indent=2, sort_keys=True))

    return "\n".join(lines)
