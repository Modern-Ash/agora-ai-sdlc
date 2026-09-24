from pathlib import Path

from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_context import select_execution_context


class Provider:
    name = "laya"

    def decide(self, state, questions):
        path = state["candidate"]["path"]
        values = {
            "src/required.py": ("required", 0.98),
            "src/noise.py": ("irrelevant", 0.97),
            "src/uncertain.py": ("irrelevant", 0.55),
        }
        value, confidence = values[path]
        return DecisionResult(
            provider="laya",
            answers={
                "relevance": DecisionAnswer(
                    question="relevance",
                    type="choice",
                    value=value,
                    confidence=confidence,
                    probabilities={value: confidence},
                )
            },
            latency_ms=2.0,
            model="typed-decisions",
        )


def bundle():
    return ExecutionBundle(
        schema="agora-ai-sdlc/execution-bundle/v1",
        swarm="delivery",
        work="issue-1",
        stage="construction",
        next_action="implement",
        branch="ai-sdlc/issue-1",
        base_branch="main",
        head="abc",
        objective="Implement bounded change",
        acceptance_criteria=("behavior works",),
        changed_paths=("src/changed.py",),
        dirty_paths=(),
        related_paths=("src/required.py", "src/noise.py", "src/uncertain.py"),
        languages=("Python",),
        build_systems=("Python",),
        verification_commands=("pytest",),
        risks=(),
        governance={},
        deterministic_inception_path=None,
    )


def test_execution_context_prunes_confident_noise_but_keeps_changed_and_uncertain(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    for name in ("changed.py", "required.py", "noise.py", "uncertain.py"):
        (src / name).write_text(("content " + name + "\n") * 100, encoding="utf-8")

    selection = select_execution_context(
        tmp_path,
        bundle(),
        provider=Provider(),
        confidence_threshold=0.90,
    )

    assert "src/changed.py" in selection.selected_paths
    assert "src/required.py" in selection.selected_paths
    assert "src/noise.py" not in selection.selected_paths
    assert "src/uncertain.py" in selection.selected_paths
    assert selection.protected_paths == ("src/changed.py",)
    assert selection.escalated_paths == ("src/uncertain.py",)
    assert selection.selected_tokens < selection.candidate_tokens
    assert selection.saved_tokens > 0


def test_execution_context_never_adds_paths_outside_deterministic_candidates(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    for name in ("changed.py", "required.py", "noise.py", "uncertain.py", "secret.py"):
        (src / name).write_text("x = 1\n", encoding="utf-8")

    selection = select_execution_context(tmp_path, bundle(), provider=Provider())

    assert "src/secret.py" not in selection.candidate_paths
    assert "src/secret.py" not in selection.selected_paths
