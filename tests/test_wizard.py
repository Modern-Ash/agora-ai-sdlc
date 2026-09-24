import json
from pathlib import Path

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.wizard import build_wizard_view, load_answers, render_wizard, save_answer


def decision(**changes):
    values = dict(
        swarm="delivery",
        work="issue-26",
        title="Implement idempotent retry",
        method="ai-sdlc",
        actor="project:developer",
        role="developer",
        state="inception",
        target="construction",
        gate="inception-approved",
        blockers=("blocked",),
        messages=("Resolve clarification.",),
        missing_artifacts=(),
        missing_evidence=(),
        missing_approvals=(),
        unsatisfied_criteria=(),
        git_issues=(),
        clarification_issues=("clarification-not-run",),
        ready_for_human_approval=False,
        ready_to_transition=False,
    )
    values.update(changes)
    return GuidedDecision(**values)


def test_wizard_extracts_material_gaps_and_persists_answers(tmp_path):
    handoff = tmp_path / ".agora/ai-sdlc/handoffs/issue-26/DETERMINISTIC_INCEPTION.md"
    handoff.parent.mkdir(parents=True)
    handoff.write_text(
        "## Material clarifications\n\n"
        "- Which API contract is authoritative\n"
        "- Should retries preserve the original idempotency key?\n\n"
        "## Level 1 Plan\n\n- continue\n",
        encoding="utf-8",
    )

    view = build_wizard_view(tmp_path, decision())
    assert view.phase == "inception"
    assert view.current_step == "clarify"
    assert [q.text for q in view.questions] == [
        "Which API contract is authoritative?",
        "Should retries preserve the original idempotency key?",
    ]

    path = save_answer(tmp_path, "issue-26", view.questions[0], "contracts/api.yaml")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["answers"]["gap-01"] == "contracts/api.yaml"
    assert load_answers(tmp_path, "issue-26")["gap-01"] == "contracts/api.yaml"

    refreshed = build_wizard_view(tmp_path, decision())
    assert [q.id for q in refreshed.questions] == ["gap-02"]


def test_wizard_presents_progress_and_full_operational_facts(tmp_path):
    view = build_wizard_view(
        tmp_path,
        decision(
            state="construction",
            clarification_issues=(),
            unsatisfied_criteria=("AC-002",),
            missing_evidence=("tests",),
        ),
    )
    rendered = render_wizard(view, lang="en")

    assert "Agora Flow · AI-DLC delivery" in rendered
    assert "▶ Construction" in rendered
    assert "▶ Testing" in rendered
    assert "Intent / objective: Implement idempotent retry" in rendered
    assert "Decision gate: inception-approved" in rendered
    assert "Missing evidence: tests" in rendered


def test_wizard_spanish_labels_do_not_hide_underlying_facts(tmp_path):
    view = build_wizard_view(tmp_path, decision(clarification_issues=(), missing_artifacts=("architecture",)))
    rendered = render_wizard(view, lang="es")

    assert "Agora Flow · delivery AI-DLC" in rendered
    assert "Qué sabe Agora" in rendered
    assert "Work: delivery/issue-26" in rendered
    assert "Decision gate: inception-approved" in rendered
