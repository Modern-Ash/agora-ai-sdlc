"""Human-friendly AI-SDLC projection over Agora Core operational state."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.i18n import t

_BLOCKER_LIST = re.compile(r"(?P<name>[a-z-]+)=\[(?P<items>[^\]]*)\]")
_LIFECYCLE_ORDER = ("readiness", "intent", "inception", "construction", "operations", "completed")


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
    observed_artifacts: tuple[str, ...] = ()
    criterion_statuses: tuple[tuple[str, tuple[str, ...]], ...] = ()
    developer_actor: str | None = None
    developer_actor_kind: str | None = None
    responsible_actor_kind: str | None = None
    required_criterion_stage: str | None = None
    next_criterion_stage: str | None = None

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
    lang: str = "en",
    missing_artifacts: tuple[str, ...] = (),
    missing_evidence: tuple[str, ...] = (),
    missing_approvals: tuple[str, ...] = (),
    unsatisfied_criteria: tuple[str, ...] = (),
    git_issues: tuple[str, ...] = (),
    clarification_issues: tuple[str, ...] = (),
) -> tuple[str, ...]:
    messages: list[str] = []
    if missing_artifacts:
        messages.append(t("guided.prepare_evidence", lang=lang, items=", ".join(missing_artifacts)))
    if unsatisfied_criteria:
        messages.append(t("guided.complete_criteria", lang=lang, items=", ".join(unsatisfied_criteria)))
    if clarification_issues:
        messages.append(t("guided.resolve_clarification", lang=lang))
    if missing_evidence:
        messages.append(t("guided.collect_evidence", lang=lang, items=", ".join(missing_evidence)))
    if git_issues:
        messages.append(t("guided.resolve_policy", lang=lang, items="; ".join(git_issues)))
    if missing_approvals:
        messages.append(t("guided.ask_approval", lang=lang, items=", ".join(missing_approvals)))
    if blockers and not messages:
        messages.append(t("guided.core_blocker", lang=lang))
    return tuple(messages)


def _preferred_target(state: str | None, target_states: list[str] | tuple[str, ...]) -> str | None:
    """Prefer forward lifecycle progress over optional rework transitions."""

    targets = tuple(str(item) for item in target_states if item)
    if not targets:
        return None
    normalized_state = (state or "").casefold()
    try:
        current_index = _LIFECYCLE_ORDER.index(normalized_state)
    except ValueError:
        return targets[0]

    forward = [
        target
        for target in targets
        if target.casefold() in _LIFECYCLE_ORDER and _LIFECYCLE_ORDER.index(target.casefold()) > current_index
    ]
    if not forward:
        return targets[0]
    return min(forward, key=lambda item: _LIFECYCLE_ORDER.index(item.casefold()))


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


def _current_branch(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip() if result.returncode == 0 else ""
    return value or None


def _next_criterion_stage(
    workspace: AgoraWorkspace,
    swarm: str,
    unsatisfied: tuple[str, ...],
    statuses: tuple[tuple[str, tuple[str, ...]], ...],
    required_stage: str | None,
) -> tuple[str | None, str | None]:
    """Resolve the next missing criterion stage and the role authorized to record it."""

    if not unsatisfied or not required_stage:
        return None, None
    try:
        contract = workspace.method_contract(swarm)
        required_index = contract.criterion_stages.index(required_stage)
    except (AttributeError, ValueError):
        return None, None

    current = dict(statuses)
    for criterion in unsatisfied:
        recorded = set(current.get(criterion, ()))
        for stage in contract.criterion_stages[: required_index + 1]:
            if stage in recorded:
                continue
            roles = tuple(contract.criterion_stage_roles.get(stage, ()) or ())
            return stage, (roles[0] if roles else None)
    return None, None


def inspect_next(
    root: Path,
    *,
    swarm: str | None = None,
    work: str | None = None,
    lang: str = "en",
) -> GuidedDecision | None:
    """Project the next Core action without mutating lifecycle state."""

    workspace = AgoraWorkspace(cwd=root)
    tasks = workspace.next_actions(swarm_id=swarm, human_only=False, limit=1000)
    if work is not None:
        tasks = [item for item in tasks if item.work_id == work]
    else:
        current = _current_branch(root)
        if current:
            records = {(item.swarm_id, item.id): item for item in workspace.list_work(swarm_id=swarm)}
            branch_tasks = [
                item for item in tasks if getattr(records.get((item.swarm_id, item.work_id)), "branch", None) == current
            ]
            if branch_tasks:
                tasks = branch_tasks
    if not tasks:
        return None

    task = tasks[0]
    blockers = tuple(task.blockers)
    parsed = _combined_blocker_details(blockers)
    target = _preferred_target(task.state, task.target_states)
    details = _transition_details(workspace, str(task.swarm_id or ""), str(task.work_id or ""), target)
    gate = details.get("gate") or {}

    missing_artifacts = tuple(gate.get("missing_artifacts") or parsed.get("missing-artifacts", ()))
    missing_evidence = tuple(gate.get("missing_evidence_types") or parsed.get("missing-evidence-types", ()))
    missing_approvals = tuple(gate.get("missing_approvals") or parsed.get("missing-approvals", ()))
    unsatisfied_criteria = tuple(gate.get("unsatisfied") or parsed.get("unsatisfied", ()))
    git_issues = tuple(gate.get("git_issues") or parsed.get("git", ()))
    clarification_issues = parsed.get("clarifications", ())

    try:
        work_record = workspace.show_work(str(task.swarm_id or ""), str(task.work_id or ""))
        observed_artifacts = tuple(getattr(work_record, "artifact_kinds", ()) or ())
        raw_statuses = getattr(work_record, "criterion_statuses", {}) or {}
        criterion_statuses = tuple(
            (str(key), tuple(str(stage) for stage in stages)) for key, stages in sorted(raw_statuses.items())
        )
    except (AttributeError, OSError, ValueError, FileNotFoundError):
        observed_artifacts = ()
        criterion_statuses = ()

    developer_actor = None
    developer_actor_kind = None
    responsible_actor = task.actor
    responsible_role = task.role
    responsible_actor_kind = getattr(task, "actor_kind", None)
    required_criterion_stage = str(gate.get("required_criterion_stage") or "") or None
    next_criterion_stage = None
    try:
        swarm_record = workspace.show_swarm(str(task.swarm_id or ""))
        assignments = getattr(swarm_record, "assignments", {}) or {}
        actors = {
            getattr(actor, "reference", None): actor
            for actor in workspace.list_actors()
            if getattr(actor, "reference", None)
        }
        developer_actor = assignments.get("developer")
        if developer_actor and developer_actor in actors:
            developer_actor_kind = str(getattr(actors[developer_actor], "kind", "") or "") or None

        technical_gaps = bool(
            missing_artifacts
            or missing_evidence
            or git_issues
            or clarification_issues
        )
        if missing_approvals and not technical_gaps and not unsatisfied_criteria:
            approval_role = missing_approvals[0]
            approval_actor = assignments.get(approval_role)
            if approval_actor:
                responsible_role = approval_role
                responsible_actor = approval_actor
                record = actors.get(approval_actor)
                responsible_actor_kind = str(getattr(record, "kind", "") or "") or None
        elif unsatisfied_criteria and not technical_gaps:
            next_criterion_stage, stage_role = _next_criterion_stage(
                workspace,
                str(task.swarm_id or ""),
                unsatisfied_criteria,
                criterion_statuses,
                required_criterion_stage,
            )
            stage_actor = assignments.get(stage_role) if stage_role else None
            if stage_role and stage_actor:
                responsible_role = stage_role
                responsible_actor = stage_actor
                record = actors.get(stage_actor)
                responsible_actor_kind = str(getattr(record, "kind", "") or "") or None
    except (AttributeError, OSError, ValueError, FileNotFoundError):
        pass

    messages = _humanize(
        blockers,
        lang=lang,
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
        actor=responsible_actor,
        role=responsible_role,
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
        observed_artifacts=observed_artifacts,
        criterion_statuses=criterion_statuses,
        developer_actor=developer_actor,
        developer_actor_kind=developer_actor_kind,
        responsible_actor_kind=responsible_actor_kind,
        required_criterion_stage=required_criterion_stage,
        next_criterion_stage=next_criterion_stage,
    )


def command_plan(decision: GuidedDecision) -> tuple[tuple[str, str], ...]:
    """Build an advisory command bundle. Commands never run from this function."""

    actor = decision.actor or "<responsible-actor>"
    commands: list[tuple[str, str]] = []
    construction_needs_executor = decision.state == "construction" and bool(
        decision.missing_artifacts or decision.missing_evidence or decision.unsatisfied_criteria
    )
    if construction_needs_executor:
        commands.append(
            (
                f"aisdlc continue --swarm {decision.swarm} --work {decision.work} --run",
                (
                    "Launch the assigned governed Construction executor with the deterministic "
                    "execution bundle; it must stop before approval or lifecycle transition."
                ),
            )
        )

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
                    f'--role {approval} --by {actor} --note "Reviewed and approved"'
                ),
                "Run only after explicit confirmation from the responsible human.",
            )
        )

    if decision.target and not (construction_needs_executor and decision.target == "inception"):
        commands.append(
            (
                (
                    "agora work transition "
                    f"--swarm {decision.swarm} --work {decision.work} --to {decision.target} --by {actor}"
                ),
                "Attempt only after a fresh Core readiness check reports the gate satisfied.",
            )
        )

    return tuple(commands)


def _status_items(decision: GuidedDecision, *, lang: str = "en") -> tuple[tuple[str, bool], ...]:
    return (
        (t("guided.required_artifacts", lang=lang), not decision.missing_artifacts),
        (t("guided.acceptance_criteria", lang=lang), not decision.unsatisfied_criteria),
        (t("guided.clarifications", lang=lang), not decision.clarification_issues),
        (t("guided.verification_evidence", lang=lang), not decision.missing_evidence),
        (t("guided.repository_policy", lang=lang), not decision.git_issues),
        (t("guided.human_approvals", lang=lang), not decision.missing_approvals),
    )


def render(
    decision: GuidedDecision | None,
    *,
    expert: bool = False,
    show_commands: bool = False,
    show_actions: bool = True,
    lang: str = "en",
) -> str:
    if decision is None:
        return "Agora AI-SDLC\n\n" + t("guided.none", lang=lang)

    lines = ["Agora AI-SDLC", ""]
    if decision.title:
        lines.append(f"{t('guided.objective', lang=lang)}: {decision.title}")
    lines.extend(
        [
            f"{t('guided.work', lang=lang)}: {decision.swarm}/{decision.work}",
            f"{t('guided.method', lang=lang)}: {decision.method or t('guided.unknown', lang=lang)}",
            f"{t('guided.stage', lang=lang)}: {decision.state or t('guided.unknown', lang=lang)}"
            + (f"  ->  {decision.target}" if decision.target else ""),
        ]
    )
    if decision.gate:
        lines.append(f"{t('guided.decision_gate', lang=lang)}: {decision.gate}")
    if decision.role:
        owner = decision.role
        if decision.actor:
            owner += f" ({decision.actor})"
        lines.append(f"{t('guided.responsible', lang=lang)}: {owner}")

    lines.extend(["", t("guided.readiness", lang=lang)])
    for label, satisfied in _status_items(decision, lang=lang):
        marker = "✓" if satisfied else "!"
        lines.append(f"  {marker} {label}")

    if decision.messages:
        lines.extend(["", t("guided.what_remains", lang=lang)])
        for index, message in enumerate(decision.messages, start=1):
            lines.append(f"  {index}. {message}")

    lines.extend(["", t("guided.boundary", lang=lang)])
    if decision.actor and decision.role:
        lines.append("  " + t("guided.authority", lang=lang, actor=decision.actor, role=decision.role))
    lines.append("  " + t("guided.ai_may", lang=lang))
    lines.append("  " + t("guided.ai_may_not", lang=lang))

    if decision.ready_for_human_approval and decision.missing_approvals:
        lines.extend(
            [
                "",
                t("guided.decision_needed", lang=lang),
                "  " + t("guided.approval_needed", lang=lang),
            ]
        )
        if show_actions:
            lines.append("  " + t("guided.actions_approval", lang=lang))
    elif decision.blocked:
        lines.extend(
            [
                "",
                t("guided.recommended", lang=lang),
                "  " + t("guided.prepare_recommendation", lang=lang),
            ]
        )
        if show_actions:
            lines.append("  " + t("guided.actions_prepare", lang=lang))
    else:
        lines.extend(["", t("guided.recommended", lang=lang), "  " + t("guided.ready_actor", lang=lang)])

    if show_commands:
        lines.extend(["", t("guided.command_bundle", lang=lang)])
        for index, (command, reason) in enumerate(command_plan(decision), start=1):
            lines.append(f"  {index}. {command}")
            lines.append(f"     {reason}")

    if expert:
        lines.extend(["", t("guided.governance_details", lang=lang)])
        if decision.blockers:
            lines.extend(f"  - {blocker}" for blocker in decision.blockers)
        else:
            lines.append("  - " + t("guided.no_blockers", lang=lang))
        lines.append("")
        lines.append(t("guided.structured", lang=lang))
        lines.append(json.dumps(decision.snapshot(), indent=2, sort_keys=True))

    return "\n".join(lines)
