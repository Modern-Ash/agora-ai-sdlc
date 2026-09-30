from types import SimpleNamespace

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.flow_decision_session import FlowDecisionSession


def bundle(objective: str = "Implement bounded feature") -> ExecutionBundle:
    return ExecutionBundle(
        schema="s",
        swarm="delivery",
        work="issue-301",
        stage="inception",
        next_action="inspect-next",
        branch=None,
        base_branch=None,
        head=None,
        objective=objective,
        acceptance_criteria=("feature works",),
        changed_paths=("src/a.py",),
        dirty_paths=(),
        related_paths=("tests/test_a.py",),
        languages=("python",),
        build_systems=("pytest",),
        verification_commands=("pytest -q",),
        risks=(),
        governance={},
        deterministic_inception_path=None,
    )


class Provider:
    name = "fake-laya"
    model = "fake-checkpoint"

    def __init__(self):
        self.calls = 0

    def decide(self, state, questions):
        self.calls += 1
        answers = {
            question.id: SimpleNamespace(
                question=question.id,
                type="choice",
                value=next(iter(question.criteria)),
                confidence=0.99,
            )
            for question in questions
        }
        return SimpleNamespace(
            provider=self.name,
            model=self.model,
            answers=answers,
            latency_ms=1.0,
            metadata={},
        )


def test_reuses_evaluation_requirements_and_policy_for_unchanged_bundle():
    provider = Provider()
    session = FlowDecisionSession(snapshot_token="sha256:core-a", provider=provider)
    work = bundle()

    first = session.evaluation(work)
    second = session.evaluation(work)
    requirements = session.requirements(work)
    policy = session.policy(work)

    assert first is second
    assert requirements is session.requirements(work)
    assert policy is session.policy(work)
    # execution decisions currently perform the established question batch plus
    # the optional planner-needed batch; all downstream projections reuse them.
    assert provider.calls == 2
    assert session.calls == 1
    assert session.hits >= 4


def test_bundle_change_invalidates_cached_advisory_evaluation():
    provider = Provider()
    session = FlowDecisionSession(snapshot_token="sha256:core-a", provider=provider)

    session.evaluation(bundle("first objective"))
    session.evaluation(bundle("changed objective"))

    assert session.calls == 2
    assert provider.calls == 4


def test_snapshot_change_invalidates_cached_advisory_evaluation():
    provider = Provider()
    session = FlowDecisionSession(snapshot_token="sha256:core-a", provider=provider)
    work = bundle()

    session.evaluation(work)
    session.snapshot_token = "sha256:core-b"
    session.evaluation(work)

    assert session.calls == 2
    assert provider.calls == 4


def test_diagnostics_are_bounded_and_explain_cache_provenance():
    provider = Provider()
    session = FlowDecisionSession(snapshot_token="sha256:core-a", provider=provider)
    work = bundle()
    session.evaluation(work)

    diagnostic = session.diagnostics(work)

    assert diagnostic["cached"] is True
    assert diagnostic["snapshot_token"] == "sha256:core-a"
    assert diagnostic["provider"] == "fake-laya"
    assert diagnostic["model"] == "fake-checkpoint"
    assert diagnostic["question_schema"] == "execution-decisions/v4"
    assert "answers" not in diagnostic
