from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.guided_session import run_interactive
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery


def decision():
    return GuidedDecision(
        swarm="delivery",
        work="first-work",
        title="Deliver first governed outcome",
        method="ai-sdlc",
        actor="project:product-owner",
        role="product-owner",
        state="readiness",
        target="intent",
        gate="readiness-approved",
        blockers=("blocked",),
        messages=("Prepare readiness.",),
        missing_artifacts=("readiness-assessment",),
        clarification_issues=("clarification-not-run",),
        missing_approvals=("product-owner",),
    )


def runtime(runtime_id, name):
    return RuntimeDiscovery(
        id=runtime_id,
        name=name,
        command=runtime_id,
        installed=True,
        executable=f"/bin/{runtime_id}",
        responsive=True,
        version="1.0",
        configured=False,
    )


def test_interactive_continue_waits_for_exit(monkeypatch):
    outputs = []
    answers = iter(["x"])
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", lambda *args, **kwargs: decision())

    result = run_interactive(
        Path("."),
        input_fn=lambda prompt: next(answers),
        output_fn=outputs.append,
    )

    assert result.reason == "exit"
    assert any("[P] Prepare with AI" in line for line in outputs)


def test_prepare_prompts_for_runtime_and_keeps_selection(monkeypatch):
    outputs = []
    answers = iter(["p", "2", "b", "x"])
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", lambda *args, **kwargs: decision())
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.discover_runtimes",
        lambda root: (runtime("codex", "Codex"), runtime("claude", "Claude Code")),
    )

    result = run_interactive(
        Path("."),
        input_fn=lambda prompt: next(answers),
        output_fn=outputs.append,
    )

    assert result.reason == "exit"
    assert result.selected_runtime == "claude"
    assert "Selected assistant: Claude Code" in outputs
    assert "Prepare with Claude Code" in outputs
    assert any("Active assistant: Claude Code" in line for line in outputs)


def test_change_agent_replaces_session_runtime(monkeypatch):
    outputs = []
    answers = iter(["c", "1", "c", "2", "x"])
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", lambda *args, **kwargs: decision())
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.discover_runtimes",
        lambda root: (runtime("codex", "Codex"), runtime("ollama", "Ollama")),
    )

    result = run_interactive(
        Path("."),
        input_fn=lambda prompt: next(answers),
        output_fn=outputs.append,
    )

    assert result.selected_runtime == "ollama"
    assert outputs.count("Selected assistant: Codex") == 1
    assert outputs.count("Selected assistant: Ollama") == 1


def test_review_and_details_are_selectable(monkeypatch):
    outputs = []
    answers = iter(["r", "d", "x"])
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", lambda *args, **kwargs: decision())

    run_interactive(
        Path("."),
        input_fn=lambda prompt: next(answers),
        output_fn=outputs.append,
    )

    assert "Readiness review" in outputs
    assert any("Structured decision" in line for line in outputs)


def test_prepare_with_no_runtime_returns_to_menu(monkeypatch):
    outputs = []
    answers = iter(["p", "x"])
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", lambda *args, **kwargs: decision())
    monkeypatch.setattr("agora_ai_sdlc.guided_session.discover_runtimes", lambda root: ())

    result = run_interactive(
        Path("."),
        input_fn=lambda prompt: next(answers),
        output_fn=outputs.append,
    )

    assert result.reason == "exit"
    assert "No responsive AI CLI runtime was detected." in outputs
