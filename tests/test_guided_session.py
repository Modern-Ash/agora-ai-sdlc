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
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.execute_guided_preparation",
        lambda *args, **kwargs: SimpleNamespace(runtime="Claude Code"),
    )
    answers = iter(["p", "2", "1", "b", "x"])
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
    assert result.selected_model is None
    assert "Selected assistant: Claude Code · configured model" in outputs
    assert "Prepare with Claude Code · configured model" in outputs
    assert any("Active assistant: Claude Code · configured model" in line for line in outputs)


def test_change_agent_replaces_session_runtime(monkeypatch):
    outputs = []
    answers = iter(["c", "1", "1", "c", "2", "1", "x"])
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

    assert result.selected_runtime == "claude"
    assert outputs.count("Selected assistant: Codex · configured model") == 1
    assert outputs.count("Selected assistant: Claude Code · configured model") == 1


def test_opencode_selection_chooses_provider_then_model_and_includes_ollama(monkeypatch):
    outputs = []
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.execute_guided_preparation",
        lambda *args, **kwargs: SimpleNamespace(runtime="OpenCode"),
    )
    answers = iter(["p", "1", "2", "b", "x"])
    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", lambda *args, **kwargs: decision())
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.discover_runtimes",
        lambda root: (
            runtime("opencode", "OpenCode"),
            runtime("ollama", "Ollama"),
        ),
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.list_available_models",
        lambda **kwargs: (
            "openai/gpt-5.5",
            "opencode/nemotron-3-ultra-free",
        ),
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.list_ollama_agent_models",
        lambda **kwargs: (
            "ollama/claude:latest",
            "ollama/gpt-oss:20b",
        ),
    )

    result = run_interactive(
        Path("."),
        input_fn=lambda prompt: next(answers),
        output_fn=outputs.append,
    )

    assert result.selected_runtime == "opencode"
    assert result.selected_model == "ollama/gpt-oss:20b"
    assert any("Step 1/2: choose the LLM/provider:" in line for line in outputs)
    assert any("Ollama (local)" in line for line in outputs)
    assert any("Step 2/2: choose the model for Ollama (local):" in line for line in outputs)
    assert any("gpt-oss:20b [local]" in line for line in outputs)


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


def test_enter_accepts_proactive_prepare_and_rechecks_core(monkeypatch):
    outputs = []
    calls = {"inspect": 0, "execute": 0}
    local = SimpleNamespace(agent="opencode", model="ollama/qwen3:8b", label="Ollama · qwen3:8b [local]")

    def inspect(*args, **kwargs):
        calls["inspect"] += 1
        return decision() if calls["inspect"] == 1 else None

    monkeypatch.setattr("agora_ai_sdlc.guided_session.inspect_next", inspect)
    monkeypatch.setattr(
        "agora_ai_sdlc.guided_session.advise_workflow",
        lambda *args, **kwargs: SimpleNamespace(
            action="prepare",
            summary="Use the local assistant.",
            source="laya",
            reasoning_tier="local",
            confidence=0.97,
            recommended_runtime=local,
        ),
    )

    def execute(*args, **kwargs):
        calls["execute"] += 1
        assert kwargs["runtime_id"] == "opencode"
        assert kwargs["model"] == "ollama/qwen3:8b"
        return SimpleNamespace(runtime="OpenCode/Ollama")

    monkeypatch.setattr("agora_ai_sdlc.guided_session.execute_guided_preparation", execute)

    result = run_interactive(
        Path("."),
        input_fn=lambda prompt: "",
        output_fn=outputs.append,
    )

    assert result.reason == "clear"
    assert calls["execute"] == 1
    assert calls["inspect"] == 2
    assert any("preselected automatically" in line for line in outputs)
    assert any("Re-reading Agora Core state" in line for line in outputs)
