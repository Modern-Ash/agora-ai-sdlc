"""Continuous AI-SDLC delivery wizard projection for Agora AI-SDLC.

The wizard is a transparent presentation/interaction layer over authoritative
Agora Core facts. It preserves AI-SDLC terminology while hiding operational
complexity, never evidence or authority boundaries.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.context_graph import load_artifacts
from agora_ai_sdlc.delivery_submission import pull_request_delivery_enabled
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.i18n import t

PHASE_ORDER = ("inception", "construction", "operations")
PULL_REQUEST_STEPS = ("change-set", "pull-request", "review-delivery")

PHASE_STEPS = {
    "inception": (
        "understand",
        "clarify",
        "level-1-plan",
        "stories",
        "nfr-risk",
        "units",
        "bolts",
    ),
    "construction": (
        "semantic-elevation",
        "domain-design",
        "logical-design",
        "implementation",
        "testing",
        "deployment-unit",
    ),
    "operations": (
        "deployment",
        "observability",
        "feedback",
    ),
}

ARTIFACT_STEP = {
    "intent": ("inception", "understand"),
    "clarification": ("inception", "clarify"),
    "plan": ("inception", "level-1-plan"),
    "requirements": ("inception", "stories"),
    "user-stories": ("inception", "stories"),
    "nfr": ("inception", "nfr-risk"),
    "risk-register": ("inception", "nfr-risk"),
    "measurement-criteria": ("inception", "nfr-risk"),
    "prfaq": ("inception", "nfr-risk"),
    "unit-of-work": ("inception", "units"),
    "bolt-plan": ("inception", "bolts"),
    "legacy-inventory": ("construction", "semantic-elevation"),
    "dependency-map": ("construction", "semantic-elevation"),
    "characterization": ("construction", "semantic-elevation"),
    "static-system-model": ("construction", "semantic-elevation"),
    "dynamic-system-model": ("construction", "semantic-elevation"),
    "domain-model": ("construction", "domain-design"),
    "logical-design": ("construction", "logical-design"),
    "architecture": ("construction", "logical-design"),
    "implementation-plan": ("construction", "implementation"),
    "test-strategy": ("construction", "testing"),
    "threat-model": ("construction", "testing"),
    "deployment-unit": ("construction", "deployment-unit"),
    "deployment-plan": ("operations", "deployment"),
    "operational-readiness": ("operations", "deployment"),
    "rollback-procedure": ("operations", "deployment"),
    "learning-record": ("operations", "feedback"),
}

METHOD_OUTPUTS = {
    "inception": (
        ("Intent", "intent"),
        ("Level 1 Plan", "plan"),
        ("User Stories", "user-stories"),
        ("NFRs", "nfr"),
        ("Risk Register", "risk-register"),
        ("Measurement Criteria", "measurement-criteria"),
        ("Units", "unit-of-work"),
        ("Suggested Bolts", "bolt-plan"),
    ),
    "construction": (
        ("Domain Design", "domain-model"),
        ("Logical Design", "logical-design"),
        ("Test Strategy", "test-strategy"),
        ("Deployment Unit", "deployment-unit"),
    ),
    "operations": (
        ("Deployment Plan", "deployment-plan"),
        ("Operational Readiness", "operational-readiness"),
        ("Rollback", "rollback-procedure"),
        ("Learning", "learning-record"),
    ),
}


@dataclass(frozen=True)
class WizardQuestion:
    id: str
    text: str
    reason: str


@dataclass(frozen=True)
class MethodOutput:
    label: str
    artifact_kind: str
    status: str  # required-now | observed | method-output


@dataclass(frozen=True)
class WizardView:
    phase: str
    current_step: str
    completed_phases: tuple[str, ...]
    upcoming_phases: tuple[str, ...]
    completed_steps: tuple[str, ...]
    upcoming_steps: tuple[str, ...]
    facts: tuple[str, ...]
    gaps: tuple[str, ...]
    questions: tuple[WizardQuestion, ...]
    evidence: tuple[str, ...]
    human_decisions: tuple[str, ...]
    method_outputs: tuple[MethodOutput, ...]
    brownfield: bool = False
    level_1_plan_preview: tuple[str, ...] = ()
    validation_checkpoint: str | None = None
    gate: str | None = None
    checkpoint_kind: str | None = None
    checkpoint_detail: str | None = None
    gate_ready: bool = False
    steps: tuple[str, ...] = ()
    delivery_target: str | None = None

    def snapshot(self) -> dict:
        return asdict(self)


def _phase(decision: GuidedDecision) -> str:
    state = (decision.state or "").casefold()
    target = (decision.target or "").casefold()
    if state in {"operations", "done", "completed", "closed"}:
        return "operations"
    if state in {"construction"}:
        return "construction"
    if target == "operations":
        return "construction"
    return "inception"


def _brownfield(decision: GuidedDecision) -> bool:
    kinds = set(decision.missing_artifacts)
    return bool(
        kinds
        & {
            "legacy-inventory",
            "dependency-map",
            "characterization",
            "static-system-model",
            "dynamic-system-model",
            "target-architecture",
            "migration-plan",
        }
    )


def _step(decision: GuidedDecision, phase: str) -> str:
    missing = tuple(decision.missing_artifacts)
    if phase == "inception":
        if decision.clarification_issues:
            return "clarify"
        for item in missing:
            mapped = ARTIFACT_STEP.get(item)
            if mapped and mapped[0] == phase:
                return mapped[1]
        if decision.unsatisfied_criteria:
            return "stories"
        return "level-1-plan"

    if phase == "construction":
        if _brownfield(decision):
            return "semantic-elevation"
        for item in missing:
            mapped = ARTIFACT_STEP.get(item)
            if mapped and mapped[0] == phase:
                return mapped[1]
        if decision.missing_evidence:
            return "testing"
        return "implementation"

    for item in missing:
        mapped = ARTIFACT_STEP.get(item)
        if mapped and mapped[0] == phase:
            return mapped[1]
    if decision.missing_evidence:
        return "observability"
    return "deployment"


def _section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n+(.*?)(?=^##\s+|\Z)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _level_1_plan_preview(root: Path, work: str, *, limit: int = 6) -> tuple[str, ...]:
    candidates = (
        root / ".agora" / "ai-sdlc" / "handoffs" / work / "DETERMINISTIC_INCEPTION.md",
        root
        / ".agora"
        / "ai-sdlc"
        / "handoffs"
        / f"issue-{work.removeprefix('issue-')}"
        / "DETERMINISTIC_INCEPTION.md",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        section = _section(text, "Level 1 Plan")
        items: list[str] = []
        for line in section.splitlines():
            value = line.strip()
            if not value.startswith("-"):
                continue
            value = value.removeprefix("-").strip()
            if value:
                items.append(value)
            if len(items) >= limit:
                break
        if items:
            return tuple(items)
    return ()


def _validation_checkpoint(decision: GuidedDecision, phase: str, step: str) -> str:
    if decision.ready_for_human_approval or decision.missing_approvals:
        return "approval-required"
    return f"{phase}:{step}"


def _visible_checkpoint(decision: GuidedDecision, step: str) -> tuple[str, str | None, bool]:
    if decision.missing_approvals:
        return "approval", decision.missing_approvals[0], False
    if decision.ready_to_transition:
        return "transition", decision.target, True
    if decision.clarification_issues:
        return "clarification", None, False
    if decision.missing_artifacts or decision.missing_evidence or decision.unsatisfied_criteria:
        return "work", step, False
    return "review", step, False


def _semantic_gaps(root: Path, work: str) -> tuple[str, ...]:
    candidates = (
        root / ".agora" / "ai-sdlc" / "handoffs" / work / "DETERMINISTIC_INCEPTION.md",
        root
        / ".agora"
        / "ai-sdlc"
        / "handoffs"
        / f"issue-{work.removeprefix('issue-')}"
        / "DETERMINISTIC_INCEPTION.md",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        section = _section(text, "Material clarifications")
        gaps = []
        for line in section.splitlines():
            value = line.strip().removeprefix("-").strip()
            if not value or value.casefold().startswith("no material clarification"):
                continue
            gaps.append(value)
        if gaps:
            return tuple(dict.fromkeys(gaps))
    return ()


def _answers_path(root: Path, work: str) -> Path:
    return root / ".agora" / "ai-sdlc" / "wizard" / work / "ANSWERS.json"


def load_answers(root: Path, work: str) -> dict[str, str]:
    path = _answers_path(root, work)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        return {}
    return {str(k): str(v) for k, v in answers.items() if str(v).strip()}


def save_answer(root: Path, work: str, question: WizardQuestion, answer: str) -> Path:
    path = _answers_path(root, work)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "agora-ai-sdlc/wizard-answers/v1", "work": work, "answers": {}}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("answers"), dict):
                payload["answers"].update(existing["answers"])
        except (OSError, json.JSONDecodeError):
            pass
    payload["answers"][question.id] = answer.strip()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _observed_artifact_kinds(root: Path, work: str) -> set[str]:
    observed: set[str] = set()
    roots = [root / ".agora", root / "docs", root / "ai-sdlc"]
    for candidate in roots:
        if not candidate.is_dir():
            continue
        try:
            for _, _, artifact in load_artifacts(candidate):
                artifact_work = str(artifact.front.get("work") or "")
                if artifact_work and artifact_work != work:
                    continue
                observed.add(artifact.kind)
        except (OSError, ValueError):
            continue
    return observed


def _method_outputs(root: Path, decision: GuidedDecision, phase: str) -> tuple[MethodOutput, ...]:
    missing = set(decision.missing_artifacts)
    observed = set(decision.observed_artifacts) | _observed_artifact_kinds(root, decision.work)
    outputs = []
    for label, kind in METHOD_OUTPUTS[phase]:
        if kind in observed:
            status = "observed"
        elif kind in missing:
            status = "required-now"
        else:
            status = "method-output"
        outputs.append(MethodOutput(label, kind, status))
    return tuple(outputs)


def _has_open_technical_obligations(decision: GuidedDecision) -> bool:
    return bool(
        decision.missing_artifacts
        or decision.unsatisfied_criteria
        or decision.missing_evidence
        or decision.git_issues
        or decision.clarification_issues
    )


def _visible_target(decision: GuidedDecision) -> str | None:
    """Hide backward Core transition candidates while technical work is still open."""

    target = (decision.target or "").casefold()
    state = (decision.state or "").casefold()
    order = {"inception": 0, "construction": 1, "operations": 2}
    if (
        state in order
        and target in order
        and order[target] < order[state]
        and _has_open_technical_obligations(decision)
    ):
        return None
    return decision.target


def build_wizard_view(root: Path, decision: GuidedDecision) -> WizardView:
    phase = _phase(decision)
    phase_index = PHASE_ORDER.index(phase)
    pr_delivery = phase == "operations" and pull_request_delivery_enabled(root)
    steps = PULL_REQUEST_STEPS if pr_delivery else PHASE_STEPS[phase]
    if pr_delivery:
        if decision.missing_artifacts:
            current = "change-set"
        elif "deployment" in decision.missing_evidence or any(
            "verified" in stages and "deployed" not in stages for _, stages in decision.criterion_statuses
        ):
            current = "pull-request"
        else:
            current = "review-delivery"
    else:
        current = _step(decision, phase)
    step_index = steps.index(current)

    facts = []
    if decision.title:
        facts.append(f"Intent / objective: {decision.title}")
    facts.append(f"Work: {decision.swarm}/{decision.work}")
    if decision.state:
        facts.append(f"Core lifecycle state: {decision.state}")
    visible_target = _visible_target(decision)
    if visible_target:
        facts.append(f"Next lifecycle target: {visible_target}")
    if decision.gate:
        facts.append(f"Decision gate: {decision.gate}")
    if decision.role:
        owner = decision.role + (f" ({decision.actor})" if decision.actor else "")
        facts.append(f"Responsible: {owner}")
    if pr_delivery:
        facts.append("Delivery target: pull-request")

    gaps = []
    gaps.extend(f"Missing artifact: {item}" for item in decision.missing_artifacts)
    gaps.extend(f"Unsatisfied criterion: {item}" for item in decision.unsatisfied_criteria)
    gaps.extend(f"Missing evidence: {item}" for item in decision.missing_evidence)
    gaps.extend(f"Repository policy: {item}" for item in decision.git_issues)

    answers = load_answers(root, decision.work)
    questions = []
    for pos, gap in enumerate(_semantic_gaps(root, decision.work), start=1):
        qid = f"gap-{pos:02d}"
        if qid in answers:
            continue
        questions.append(
            WizardQuestion(
                id=qid,
                text=gap.rstrip("?") + "?",
                reason="This answer removes a material ambiguity before AI enriches the next artifact.",
            )
        )

    evidence = []
    if answers:
        evidence.append(f"{len(answers)} human clarification answer(s) persisted as Work context.")
    if not decision.missing_artifacts:
        evidence.append("Current gate reports no required artifact missing.")
    if not decision.missing_evidence:
        evidence.append("Current gate reports no verification evidence missing.")
    if not decision.git_issues:
        evidence.append("Repository policy has no reported blocker.")

    checkpoint_kind, checkpoint_detail, gate_ready = _visible_checkpoint(decision, current)

    human = []
    human.extend(f"Approval required from: {item}" for item in decision.missing_approvals)
    if decision.ready_for_human_approval and not _has_open_technical_obligations(decision):
        human.append("Technical obligations are complete; human validation is the next loss-function checkpoint.")

    return WizardView(
        phase=phase,
        current_step=current,
        completed_phases=PHASE_ORDER[:phase_index],
        upcoming_phases=PHASE_ORDER[phase_index + 1 :],
        completed_steps=steps[:step_index],
        upcoming_steps=steps[step_index + 1 :],
        facts=tuple(facts),
        gaps=tuple(gaps),
        questions=tuple(questions),
        evidence=tuple(evidence),
        human_decisions=tuple(human),
        method_outputs=_method_outputs(root, decision, phase),
        brownfield=_brownfield(decision),
        level_1_plan_preview=_level_1_plan_preview(root, decision.work),
        validation_checkpoint=_validation_checkpoint(decision, phase, current),
        gate=decision.gate,
        checkpoint_kind=checkpoint_kind,
        checkpoint_detail=checkpoint_detail,
        gate_ready=gate_ready,
        steps=steps,
        delivery_target="pull-request" if pr_delivery else None,
    )


def _render_phase_bar(view: WizardView, *, lang: str) -> str:
    values = []
    for phase in PHASE_ORDER:
        if phase in view.completed_phases:
            marker = "✓"
        elif phase == view.phase:
            marker = "▶"
        else:
            marker = "·"
        values.append(f"{marker} {t(f'wizard.phase.{phase}', lang=lang)}")
    return "  " + "  →  ".join(values)


def _render_step_bar(view: WizardView, *, lang: str) -> str:
    values = []
    steps = view.steps or PHASE_STEPS[view.phase]
    for step in steps:
        if step in view.completed_steps:
            marker = "✓"
        elif step == view.current_step:
            marker = "▶"
        else:
            marker = "·"
        values.append(f"{marker} {t(f'wizard.step.{step}', lang=lang)}")
    return "  " + "  →  ".join(values)


def _localized_dynamic(item: str, *, lang: str) -> str:
    if item.startswith(("Work: ", "Decision gate: ")):
        return item

    prefixes = {
        "Intent / objective: ": "wizard.fact.intent",
        "Work: ": "wizard.fact.work",
        "Core lifecycle state: ": "wizard.fact.state",
        "Next lifecycle target: ": "wizard.fact.target",
        "Decision gate: ": "wizard.fact.gate",
        "Responsible: ": "wizard.fact.responsible",
        "Delivery target: ": "wizard.fact.delivery_target",
        "Missing artifact: ": "wizard.gap.artifact",
        "Unsatisfied criterion: ": "wizard.gap.criterion",
        "Missing evidence: ": "wizard.gap.evidence",
        "Repository policy: ": "wizard.gap.policy",
        "Approval required from: ": "wizard.human.approval",
    }
    for prefix, key in prefixes.items():
        if item.startswith(prefix):
            return t(key, lang=lang, value=item.removeprefix(prefix))
    if item.endswith(" human clarification answer(s) persisted as Work context."):
        count = item.split(" ", 1)[0]
        return t("wizard.evidence.answers", lang=lang, count=count)
    exact = {
        "Current gate reports no required artifact missing.": "wizard.evidence.no_artifact",
        "Current gate reports no verification evidence missing.": "wizard.evidence.no_evidence",
        "Repository policy has no reported blocker.": "wizard.evidence.no_policy",
        "Technical obligations are complete; human validation is the next loss-function checkpoint.": "wizard.human.validation_next",
    }
    key = exact.get(item)
    return t(key, lang=lang) if key else item


def _localized_checkpoint(value: str, *, lang: str) -> str:
    if value == "approval-required":
        return t("wizard.checkpoint.approval", lang=lang)
    phase, _, step = value.partition(":")
    return t(
        f"wizard.checkpoint.{phase}",
        lang=lang,
        step=t(f"wizard.step.{step}", lang=lang),
    )


def _render_progress_header(view: WizardView, *, lang: str) -> list[str]:
    phase_number = len(view.completed_phases) + 1
    total_phases = len(PHASE_ORDER)
    width = 10
    filled = min(width, round(width * phase_number / total_phases))
    gauge = "█" * filled + "░" * (width - filled)
    phase_name = t(f"wizard.phase.{view.phase}", lang=lang)

    steps = view.steps or PHASE_STEPS[view.phase]
    step_number = len(view.completed_steps) + 1
    total_steps = len(steps)
    step_percent = round(step_number * 100 / total_steps)
    step_width = 28
    step_filled = min(step_width, round(step_width * step_number / total_steps))
    step_gauge = "█" * step_filled + "░" * (step_width - step_filled)
    step_name = t(f"wizard.step.{view.current_step}", lang=lang)

    kind_key = f"wizard.progress.kind.{view.checkpoint_kind or 'review'}"
    kind = t(kind_key, lang=lang)
    if kind == kind_key:
        kind = (view.checkpoint_kind or "review").upper()
    detail = view.checkpoint_detail
    checkpoint = f"{kind} · {detail}" if detail else kind

    gate_status = t("wizard.progress.ready" if view.gate_ready else "wizard.progress.pending", lang=lang)
    gate = view.gate or "-"

    return [
        (
            f"│ {t('wizard.progress.global', lang=lang)}: [{gauge}] "
            f"{t('wizard.progress.phase', lang=lang, current=phase_number, total=total_phases, phase=phase_name)}"
        ),
        f"│ {phase_name}: [{step_gauge}] {step_number}/{total_steps} · {step_percent}%",
        f"│ {t('wizard.current_step', lang=lang).upper()}: {step_number:02d} · {step_name}",
        f"│ {t('wizard.progress.checkpoint', lang=lang)} · {checkpoint}",
        f"│ {t('wizard.progress.gate', lang=lang)}: {gate} · {gate_status}",
    ]


def render_wizard(view: WizardView, *, lang: str = "en") -> str:
    lines = [
        "╭─ " + t("wizard.title", lang=lang),
        *_render_progress_header(view, lang=lang),
        "│",
        _render_phase_bar(view, lang=lang),
        "│",
        (
            f"│ {t('wizard.phase_label', lang=lang)}: {t(f'wizard.phase.{view.phase}', lang=lang)} "
            f"· {len(view.completed_steps) + 1}/{len(view.steps or PHASE_STEPS[view.phase])}"
        ),
        _render_step_bar(view, lang=lang),
        f"│ {t('wizard.method_guide', lang=lang)}: {t(f'wizard.help.{view.current_step}', lang=lang)}",
        "╰" + "─" * 72,
        "",
        t("wizard.knows", lang=lang),
        *[f"  • {_localized_dynamic(item, lang=lang)}" for item in view.facts],
    ]
    if view.brownfield:
        lines.extend(
            [
                "",
                t("wizard.brownfield", lang=lang),
                "  • " + t("wizard.semantic_elevation", lang=lang),
            ]
        )
    if view.gaps:
        lines.extend(
            [
                "",
                t("wizard.open_gaps", lang=lang),
                *[f"  ! {_localized_dynamic(item, lang=lang)}" for item in view.gaps],
            ]
        )
    if view.evidence:
        lines.extend(
            [
                "",
                t("wizard.evidence", lang=lang),
                *[f"  ✓ {_localized_dynamic(item, lang=lang)}" for item in view.evidence],
            ]
        )

    if view.level_1_plan_preview:
        lines.extend(["", t("wizard.level1_preview", lang=lang)])
        for index, item in enumerate(view.level_1_plan_preview, start=1):
            lines.append(f"  {index}. {item}")

    lines.extend(["", t("wizard.method_outputs", lang=lang)])
    for item in view.method_outputs:
        marker = "!" if item.status == "required-now" else ("✓" if item.status == "observed" else "·")
        label = t(f"wizard.artifact.{item.artifact_kind}", lang=lang)
        lines.append(f"  {marker} {label:<22} [{item.artifact_kind}]")

    if view.validation_checkpoint:
        lines.extend(
            [
                "",
                t("wizard.validation_checkpoint", lang=lang),
                "  ◆ " + _localized_checkpoint(view.validation_checkpoint, lang=lang),
            ]
        )
    if view.human_decisions:
        lines.extend(
            [
                "",
                t("wizard.human_boundary", lang=lang),
                *[f"  ◆ {_localized_dynamic(item, lang=lang)}" for item in view.human_decisions],
            ]
        )
    return "\n".join(lines)
