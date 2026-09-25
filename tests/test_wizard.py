import json

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.wizard import build_wizard_view, load_answers, render_wizard, save_answer


def decision(**changes):
    values = {
        "swarm": "delivery",
        "work": "issue-26",
        "title": "Implement idempotent retry",
        "method": "ai-sdlc",
        "actor": "project:developer",
        "role": "developer",
        "state": "inception",
        "target": "construction",
        "gate": "inception-approved",
        "blockers": ("blocked",),
        "messages": ("Resolve clarification.",),
        "missing_artifacts": (),
        "missing_evidence": (),
        "missing_approvals": (),
        "unsatisfied_criteria": (),
        "git_issues": (),
        "clarification_issues": ("clarification-not-run",),
        "ready_for_human_approval": False,
        "ready_to_transition": False,
    }
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

    assert "Agora Flow · AI-SDLC delivery" in rendered
    assert "▶ Construction" in rendered
    assert "▶ Testing" in rendered
    assert "Intent / objective: Implement idempotent retry" in rendered
    assert "Decision gate: inception-approved" in rendered
    assert "Missing evidence: tests" in rendered


def test_wizard_spanish_labels_do_not_hide_underlying_facts(tmp_path):
    view = build_wizard_view(tmp_path, decision(clarification_issues=(), missing_artifacts=("architecture",)))
    rendered = render_wizard(view, lang="es")

    assert "Agora Flow · delivery AI-SDLC" in rendered
    assert "Qué sabe Agora" in rendered
    assert "Work: delivery/issue-26" in rendered
    assert "Decision gate: inception-approved" in rendered


def test_wizard_shows_level_1_plan_preview_and_validation_checkpoint(tmp_path):
    handoff = tmp_path / ".agora/ai-sdlc/handoffs/issue-26/DETERMINISTIC_INCEPTION.md"
    handoff.parent.mkdir(parents=True)
    handoff.write_text(
        "## Material clarifications\n\n- No material clarification detected from the explicit issue.\n\n"
        "## Level 1 Plan\n\n"
        "- clarify scope: execute — validate intent\n"
        "- model domain: execute — define business model\n"
        "- implement: execute — generate bounded code\n"
        "- verify: execute — collect evidence\n",
        encoding="utf-8",
    )

    view = build_wizard_view(tmp_path, decision(clarification_issues=()))
    assert view.level_1_plan_preview[:2] == (
        "clarify scope: execute — validate intent",
        "model domain: execute — define business model",
    )
    assert view.validation_checkpoint is not None

    rendered = render_wizard(view, lang="en")
    assert "Level 1 Plan · current proposal" in rendered
    assert "Human validation checkpoint" in rendered
    assert "implement: execute" in rendered


def test_wizard_hides_backward_target_while_construction_obligations_are_open(tmp_path):
    view = build_wizard_view(
        tmp_path,
        decision(
            state="construction",
            target="inception",
            clarification_issues=(),
            missing_artifacts=("domain-model",),
            missing_evidence=("test-suite",),
            ready_for_human_approval=True,
        ),
    )

    assert "Core lifecycle state: construction" in view.facts
    assert not any(item == "Next lifecycle target: inception" for item in view.facts)
    assert not any("Technical obligations are complete" in item for item in view.human_decisions)


def test_wizard_keeps_forward_target_when_progression_is_valid(tmp_path):
    view = build_wizard_view(
        tmp_path,
        decision(
            state="construction",
            target="operations",
            clarification_issues=(),
            missing_artifacts=(),
            missing_evidence=(),
            ready_for_human_approval=True,
        ),
    )

    assert "Next lifecycle target: operations" in view.facts
    assert any("Technical obligations are complete" in item for item in view.human_decisions)


def test_wizard_progress_header_distinguishes_approval_roles_and_transition(tmp_path):
    po_view = build_wizard_view(
        tmp_path,
        decision(
            clarification_issues=(),
            role="product-owner",
            actor="project:product-owner",
            missing_approvals=("product-owner", "developer"),
            ready_for_human_approval=True,
        ),
    )
    po_rendered = render_wizard(po_view, lang="es")

    assert "Progreso global: [███░░░░░░░] Fase 1/3 · Inception" in po_rendered
    assert "CHECKPOINT · APROBACIÓN · product-owner" in po_rendered
    assert "Gate: inception-approved · PENDIENTE" in po_rendered

    dev_view = build_wizard_view(
        tmp_path,
        decision(
            clarification_issues=(),
            role="developer",
            actor="project:ai-runtime-2",
            missing_approvals=("developer",),
            ready_for_human_approval=True,
        ),
    )
    dev_rendered = render_wizard(dev_view, lang="es")

    assert "CHECKPOINT · APROBACIÓN · developer" in dev_rendered
    assert "CHECKPOINT · APROBACIÓN · product-owner" not in dev_rendered

    transition_view = build_wizard_view(
        tmp_path,
        decision(
            clarification_issues=(),
            missing_approvals=(),
            ready_for_human_approval=False,
            ready_to_transition=True,
        ),
    )
    transition_rendered = render_wizard(transition_view, lang="es")

    assert "CHECKPOINT · TRANSICIÓN · construction" in transition_rendered
    assert "Gate: inception-approved · LISTO" in transition_rendered
