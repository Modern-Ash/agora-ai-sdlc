from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.guided_session import run_interactive
from agora_ai_sdlc.wizard import WizardQuestion, WizardView


def decision(**changes):
    values = {
        "swarm": "delivery",
        "work": "first-work",
        "title": "Deliver first governed outcome",
        "method": "ai-sdlc",
        "actor": "project:developer",
        "role": "developer",
        "state": "construction",
        "target": "operations",
        "gate": "construction-complete",
        "blockers": ("blocked",),
        "messages": ("Prepare missing work.",),
        "missing_artifacts": ("implementation-plan",),
        "clarification_issues": (),
        "missing_approvals": (),
    }
    values.update(changes)
    return GuidedDecision(**values)


def view(*, questions=()):
    return WizardView(
        phase="construction",
        current_step="implementation",
        completed_phases=("inception",),
        upcoming_phases=("operations",),
        completed_steps=("semantic-elevation", "domain-design", "logical-design"),
        upcoming_steps=("testing", "deployment-unit"),
        facts=("Objective: Deliver first governed outcome", "Work: delivery/first-work"),
        gaps=("Missing artifact: implementation-plan",),
        questions=tuple(questions),
        evidence=("Repository policy has no reported blocker.",),
        human_decisions=(),
        method_outputs=(),
        brownfield=False,
    )


def advice(runtime=None):
    return SimpleNamespace(
        action="prepare",
        summary="Prepare the missing work.",
        source="laya",
        reasoning_tier="local",
        confidence=0.97,
        recommended_runtime=runtime,
    )


def test_wizard_shows_progress_information_and_single_confirmation(monkeypatch):
    outputs = []
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", lambda *args, **kwargs: decision())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", lambda *args, **kwargs: advice())

    result = run_interactive(Path("."), input_fn=lambda prompt: "x", output_fn=outputs.append)

    assert result.reason == "exit"
    assert any("Agora Flow · AI-SDLC delivery" in line for line in outputs)
    assert any("What Agora knows" in line for line in outputs)
    assert "[Enter] Confirm  [A] Adjust  [D] Details  [X] Exit" in outputs


def test_material_gap_is_asked_inline_and_saved_without_another_command(monkeypatch, tmp_path):
    outputs = []
    calls = {"inspect": 0, "save": 0}

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return decision(clarification_issues=("material-gap",)) if calls["inspect"] == 1 else None

    question = WizardQuestion("gap-01", "Which API contract is authoritative?", "Removes ambiguity.")
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.build_wizard_view",
        lambda *args, **kwargs: view(questions=(question,)),
    )

    def save(root, work, q, answer):
        calls["save"] += 1
        assert q.id == "gap-01"
        assert answer == "OpenAPI v3 in contracts/api.yaml"
        path = root / ".agora/ai-sdlc/wizard/first-work/ANSWERS.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        return path

    monkeypatch.setattr("agora_ai_sdlc.guided_session.save_answer", save)

    result = run_interactive(
        tmp_path,
        input_fn=lambda prompt: "OpenAPI v3 in contracts/api.yaml",
        output_fn=outputs.append,
    )

    assert result.reason == "clear"
    assert calls["save"] == 1
    assert any("Which API contract is authoritative?" in line for line in outputs)
    assert any("Recalculating the delivery path" in line for line in outputs)


def test_enter_confirms_recommended_action_executes_and_rechecks_core(monkeypatch):
    outputs = []
    calls = {"inspect": 0, "execute": 0}
    runtime = SimpleNamespace(agent="opencode", model="ollama/qwen3:8b", label="Ollama · qwen3:8b [local]")

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return decision() if calls["inspect"] == 1 else None

    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", lambda *args, **kwargs: advice(runtime))

    def execute(*args, **kwargs):
        calls["execute"] += 1
        assert kwargs["runtime_id"] == "opencode"
        assert kwargs["model"] == "ollama/qwen3:8b"
        return SimpleNamespace(runtime="OpenCode/Ollama")

    monkeypatch.setattr("agora_ai_sdlc.guided_session.execute_guided_preparation", execute)

    result = run_interactive(Path("."), input_fn=lambda prompt: "", output_fn=outputs.append)

    assert result.reason == "clear"
    assert calls == {"inspect": 2, "execute": 1}
    assert any("If confirmed, Agora will" in line for line in outputs)
    assert any("Re-reading Agora Core state" in line for line in outputs)


def test_details_keep_full_governance_visible(monkeypatch):
    outputs = []
    answers = iter(["d", "x"])
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", lambda *args, **kwargs: decision())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", lambda *args, **kwargs: advice())

    result = run_interactive(Path("."), input_fn=lambda prompt: next(answers), output_fn=outputs.append)

    assert result.reason == "exit"
    assert any("Structured decision" in line for line in outputs)
    assert any("Underlying command bundle" in line for line in outputs)


def test_failed_runtime_is_not_reselected_automatically(monkeypatch):
    outputs = []
    calls = {"inspect": 0, "select": 0, "execute": 0}
    runtime = SimpleNamespace(agent="claude", model=None, label="Claude Code · configured model")

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return decision() if calls["inspect"] < 4 else None

    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", lambda *args, **kwargs: advice(runtime))

    def execute(*args, **kwargs):
        calls["execute"] += 1
        raise ValueError("Actor not found: ai-claude")

    monkeypatch.setattr("agora_ai_sdlc.guided_session.execute_guided_preparation", execute)

    def select(*args, **kwargs):
        calls["select"] += 1

    monkeypatch.setattr("agora_ai_sdlc.guided_session._select_runtime", select)

    answers = iter(["", "", "x"])
    result = run_interactive(Path("."), input_fn=lambda prompt: next(answers), output_fn=outputs.append)

    assert result.reason == "exit"
    assert calls["execute"] == 1
    assert calls["select"] == 1
    assert any("Actor not found: ai-claude" in line for line in outputs)
