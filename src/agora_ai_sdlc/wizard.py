"""Continuous delivery wizard projection for Agora AI-SDLC.

The wizard is presentation and interaction state over authoritative Core facts.
It never invents lifecycle state or approval.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.guided import GuidedDecision

STEP_ORDER = ("understand", "clarify", "plan", "build", "verify", "review", "done")
STEP_LABELS = {
    "understand": "Understand",
    "clarify": "Clarify",
    "plan": "Plan",
    "build": "Build",
    "verify": "Verify",
    "review": "Review",
    "done": "Done",
}


@dataclass(frozen=True)
class WizardQuestion:
    id: str
    text: str
    reason: str


@dataclass(frozen=True)
class WizardView:
    current_step: str
    completed_steps: tuple[str, ...]
    upcoming_steps: tuple[str, ...]
    facts: tuple[str, ...]
    gaps: tuple[str, ...]
    questions: tuple[WizardQuestion, ...]
    evidence: tuple[str, ...]
    human_decisions: tuple[str, ...]

    def snapshot(self) -> dict:
        return asdict(self)


def _step(decision: GuidedDecision) -> str:
    state = (decision.state or "").casefold()
    if decision.ready_for_human_approval or decision.missing_approvals:
        return "review"
    if decision.missing_evidence:
        return "verify"
    if decision.unsatisfied_criteria:
        return "build"
    if decision.clarification_issues:
        return "clarify"
    if decision.missing_artifacts:
        if state in {"readiness", "intent", "inception"}:
            return "plan"
        return "build"
    if decision.ready_to_transition:
        return "review"
    if state in {"operations", "done", "completed", "closed"}:
        return "done"
    if state in {"construction"}:
        return "build"
    return "understand"


def _section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n+(.*?)(?=^##\s+|\Z)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _semantic_gaps(root: Path, work: str) -> tuple[str, ...]:
    candidates = (
        root / ".agora" / "ai-sdlc" / "handoffs" / work / "DETERMINISTIC_INCEPTION.md",
        root / ".agora" / "ai-sdlc" / "handoffs" / f"issue-{work.removeprefix('issue-')}" / "DETERMINISTIC_INCEPTION.md",
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


def build_wizard_view(root: Path, decision: GuidedDecision) -> WizardView:
    current = _step(decision)
    index = STEP_ORDER.index(current)
    completed = STEP_ORDER[:index]
    upcoming = STEP_ORDER[index + 1 :]

    facts = []
    if decision.title:
        facts.append(f"Objective: {decision.title}")
    facts.append(f"Work: {decision.swarm}/{decision.work}")
    if decision.state:
        facts.append(f"Current lifecycle state: {decision.state}")
    if decision.target:
        facts.append(f"Next lifecycle target: {decision.target}")
    if decision.gate:
        facts.append(f"Gate: {decision.gate}")
    if decision.role:
        facts.append(f"Responsible role: {decision.role}")

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
                reason="This answer removes a material ambiguity before implementation.",
            )
        )

    evidence = []
    if not decision.missing_artifacts:
        evidence.append("Required artifacts are present.")
    if not decision.missing_evidence:
        evidence.append("No verification evidence is currently missing.")
    if not decision.git_issues:
        evidence.append("Repository policy has no reported blocker.")

    human = []
    human.extend(f"Approval required from: {item}" for item in decision.missing_approvals)
    if decision.ready_for_human_approval:
        human.append("Technical obligations are complete; human confirmation is the next boundary.")

    return WizardView(
        current_step=current,
        completed_steps=tuple(completed),
        upcoming_steps=tuple(upcoming),
        facts=tuple(facts),
        gaps=tuple(gaps),
        questions=tuple(questions),
        evidence=tuple(evidence),
        human_decisions=tuple(human),
    )


def render_wizard(view: WizardView) -> str:
    progress = []
    for step in STEP_ORDER:
        if step in view.completed_steps:
            marker = "✓"
        elif step == view.current_step:
            marker = "▶"
        else:
            marker = "·"
        progress.append(f"{marker} {STEP_LABELS[step]}")
    lines = [
        "Delivery wizard",
        "  " + "  →  ".join(progress),
        "",
        f"Current step: {STEP_LABELS[view.current_step]}",
        "",
        "What Agora knows",
        *[f"  • {item}" for item in view.facts],
    ]
    if view.gaps:
        lines.extend(["", "Open gaps", *[f"  ! {item}" for item in view.gaps]])
    if view.evidence:
        lines.extend(["", "Evidence", *[f"  ✓ {item}" for item in view.evidence]])
    if view.human_decisions:
        lines.extend(["", "Human boundary", *[f"  • {item}" for item in view.human_decisions]])
    return "\n".join(lines)
