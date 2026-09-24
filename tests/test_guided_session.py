from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.guided_session import _ProgressDisplay, run_interactive
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
        return SimpleNamespace(runtime="OpenCode/Ollama", result_path="/tmp/RESULT.md")

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


def test_failed_runtime_recovers_inside_same_decision_without_rerunning_laya(monkeypatch):
    outputs = []
    calls = {"inspect": 0, "advice": 0, "select": 0, "execute": 0}
    claude = SimpleNamespace(agent="claude", model=None, label="Claude Code · configured model")
    ollama = SimpleNamespace(
        agent="opencode",
        model="ollama/qwen3:8b",
        label="Ollama (local via OpenCode) · ollama/qwen3:8b [local]",
    )

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return decision() if calls["inspect"] == 1 else None

    def advise_once(*args, **kwargs):
        calls["advice"] += 1
        return advice(claude)

    def execute(*args, **kwargs):
        calls["execute"] += 1
        if calls["execute"] == 1:
            assert kwargs["runtime_id"] == "claude"
            raise ValueError(
                "Guided executor Claude Code failed: Session runner exited with code 1. "
                "Durable diagnostics: /tmp/claude/SUMMARY.md. Resume with: agora resume --session test. "
                "Executor diagnostic: You've hit your weekly limit · resets 4pm."
            )
        assert kwargs["runtime_id"] == "opencode"
        assert kwargs["model"] == "ollama/qwen3:8b"
        return SimpleNamespace(runtime="OpenCode", result_path="/tmp/RESULT.md")

    def select(*args, **kwargs):
        calls["select"] += 1
        return ollama

    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", advise_once)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.execute_guided_preparation", execute)
    monkeypatch.setattr("agora_ai_sdlc.guided_session._select_runtime", select)

    answers = iter(["", "a", ""])
    result = run_interactive(Path("."), input_fn=lambda prompt: next(answers), output_fn=outputs.append)

    assert result.reason == "clear"
    assert calls == {"inspect": 2, "advice": 1, "select": 1, "execute": 2}
    assert any("Claude Code · configured model failed" in line for line in outputs)
    assert any("You've hit your weekly limit" in line for line in outputs)
    assert any("Durable diagnostics: /tmp/claude/SUMMARY.md" in line for line in outputs)
    assert any("Decision preserved" in line for line in outputs)
    assert not any("Session runner exited with code 1" in line for line in outputs)
    assert any("Confirm and run with Ollama" in line for line in outputs)


def test_invalid_confirmation_does_not_reinspect_or_rerun_laya(monkeypatch):
    outputs = []
    calls = {"inspect": 0, "advice": 0}

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return decision()

    def advise(*args, **kwargs):
        calls["advice"] += 1
        return advice_result

    advice_result = advice()
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", advise)

    answers = iter(["invalid", "x"])
    result = run_interactive(Path("."), input_fn=lambda prompt: next(answers), output_fn=outputs.append)

    assert result.reason == "exit"
    assert calls == {"inspect": 1, "advice": 1}
    assert any("Choose Enter, A, D or X." in line for line in outputs)


def test_review_boundary_stops_session_without_recomputing(monkeypatch):
    outputs = []
    calls = {"inspect": 0, "advice": 0}

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return decision(missing_artifacts=(), blockers=())

    def advise_review(*args, **kwargs):
        calls["advice"] += 1
        return SimpleNamespace(
            action="review",
            summary="Review evidence.",
            source="deterministic",
            reasoning_tier=None,
            confidence=None,
            recommended_runtime=None,
        )

    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", advise_review)

    result = run_interactive(Path("."), input_fn=lambda prompt: "", output_fn=outputs.append)

    assert result.reason == "review"
    assert calls == {"inspect": 1, "advice": 1}
    assert any("No approval was recorded." in line for line in outputs)


def test_progress_display_deduplicates_repeated_heartbeat_for_non_tty():
    outputs = []
    progress = _ProgressDisplay(
        output_fn=outputs.append,
        lang="es",
        runtime="Ollama (local via OpenCode) · ollama/qwen3-coder:latest [local]",
    )

    progress.start()
    progress.update("context")
    progress.update("executor")
    progress.update("executor_wait")
    progress.update("executor_wait")
    progress.stop()

    assert len(outputs) == 3
    assert outputs[0] == "Preparando contexto de ejecución acotado con Laya…"
    assert outputs[1].startswith("Iniciando Ollama (local via OpenCode)")
    assert outputs[2] == "El executor sigue activo; Agora Core espera que termine la sesión gobernada…"


def test_successful_executor_without_core_progress_stops_instead_of_looping(monkeypatch):
    outputs = []
    calls = {"inspect": 0, "advice": 0, "execute": 0}
    runtime = SimpleNamespace(
        agent="opencode",
        model="ollama/qwen3-coder:latest",
        label="Ollama (local via OpenCode) · ollama/qwen3-coder:latest [local]",
    )
    current = decision()

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return current

    def advise_once(*args, **kwargs):
        calls["advice"] += 1
        return advice(runtime)

    def execute(*args, **kwargs):
        calls["execute"] += 1
        return SimpleNamespace(
            runtime="OpenCode",
            result_path="/tmp/RESULT.md",
        )

    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", advise_once)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.execute_guided_preparation", execute)

    result = run_interactive(Path("."), input_fn=lambda prompt: "", output_fn=outputs.append)

    assert result.reason == "no-progress"
    assert calls == {"inspect": 2, "advice": 1, "execute": 1}
    assert any("no governed progress" in line for line in outputs)
    assert any("/tmp/RESULT.md" in line for line in outputs)


def test_adjusted_runtime_is_explicit_at_confirmation_boundary(monkeypatch):
    outputs = []
    calls = {"inspect": 0, "advice": 0, "execute": 0}
    claude = SimpleNamespace(agent="claude", model=None, label="Claude Code · configured model")

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return decision() if calls["inspect"] == 1 else None

    def advise_once(*args, **kwargs):
        calls["advice"] += 1
        return advice()

    def execute(*args, **kwargs):
        calls["execute"] += 1
        assert kwargs["runtime_id"] == "claude"
        assert kwargs["model"] is None
        return SimpleNamespace(runtime="Claude Code", result_path="/tmp/RESULT.md")

    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.build_wizard_view", lambda *args, **kwargs: view())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", advise_once)
    monkeypatch.setattr("agora_ai_sdlc.guided_session._select_runtime", lambda *args, **kwargs: claude)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.execute_guided_preparation", execute)

    answers = iter(["a", ""])
    result = run_interactive(Path("."), input_fn=lambda prompt: next(answers), output_fn=outputs.append)

    assert result.reason == "clear"
    assert calls == {"inspect": 2, "advice": 1, "execute": 1}
    assert any("[Enter] Confirm and run with Claude Code · configured model" in line for line in outputs)
