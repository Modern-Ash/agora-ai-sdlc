from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_decisions import advise_execution


class CountingProvider:
    name = "counting"
    model = "test"

    def __init__(self, *, joint: bool):
        self.calls = 0
        self.supports_joint_execution_questions = joint

    def decide(self, state, questions):
        self.calls += 1
        values = {
            "reasoning_tier": "local",
            "security_review": "normal",
            "change_risk": "low",
            "validation_focus": "functional",
            "planner_needed": "none",
        }
        return DecisionResult(
            provider=self.name,
            model=self.model,
            answers={
                question.id: DecisionAnswer(
                    question=question.id,
                    type=question.type,
                    value=values[question.id],
                    confidence=0.99,
                )
                for question in questions
            },
        )


def bundle():
    return ExecutionBundle(
        schema="s",
        swarm="delivery",
        work="issue-x",
        stage="construction",
        next_action="inspect-next",
        branch=None,
        base_branch=None,
        head=None,
        objective="bounded change",
        acceptance_criteria=("tests pass",),
        changed_paths=(),
        dirty_paths=(),
        related_paths=("src/example.py",),
        languages=("python",),
        build_systems=(),
        verification_commands=("pytest",),
        risks=(),
        governance={},
        deterministic_inception_path=None,
    )


def test_joint_provider_batches_planner_into_single_system1_call():
    provider = CountingProvider(joint=True)

    evaluated = advise_execution(bundle(), provider=provider)

    assert provider.calls == 1
    assert evaluated.result.answers["planner_needed"].value == "none"
    assert evaluated.result.metadata["provider_calls"] == 1
    assert evaluated.result.metadata["planner_batched"] is True


def test_legacy_provider_keeps_backward_compatible_separate_planner_call():
    provider = CountingProvider(joint=False)

    evaluated = advise_execution(bundle(), provider=provider)

    assert provider.calls == 2
    assert evaluated.result.answers["planner_needed"].value == "none"
    assert evaluated.result.metadata["provider_calls"] == 2
    assert evaluated.result.metadata["planner_batched"] is False
