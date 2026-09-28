from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_decisions import advise_execution
from agora_ai_sdlc.system0_decisions import threshold_for


def bundle(*, stage="construction", next_action="inspect-next", risks=(), governance=None):
    return ExecutionBundle(
        schema="s", swarm="s", work="w", stage=stage, next_action=next_action, branch=None, base_branch=None,
        head=None, objective="o", acceptance_criteria=("works",), changed_paths=(), dirty_paths=(), related_paths=(),
        languages=(), build_systems=(), verification_commands=(), risks=tuple(risks),
        governance=governance or {}, deterministic_inception_path=None,
    )  # fmt: skip


class RecordingProvider:
    name = "laya"
    model = "test"

    def __init__(self, confidence=0.99):
        self.confidence = confidence
        self.question_ids = []

    def decide(self, state, questions):
        self.question_ids.extend(q.id for q in questions)
        defaults = {
            "reasoning_tier": "local",
            "security_review": "normal",
            "change_risk": "low",
            "validation_focus": "functional",
            "planner_needed": "none",
        }
        answers = {
            q.id: DecisionAnswer(q.id, q.type, defaults[q.id], self.confidence)
            for q in questions
        }
        return DecisionResult(self.name, answers, model=self.model)


def test_human_authority_is_resolved_before_laya():
    provider = RecordingProvider()
    work = bundle(next_action="human-approval", governance={"human_approval_required": True})

    evaluation = advise_execution(work, provider=provider)

    assert evaluation.result.answers["reasoning_tier"].value == "human"
    assert "reasoning_tier" not in provider.question_ids
    assert "planner_needed" not in provider.question_ids
    assert evaluation.result.metadata["system0"]["reasoning_tier"] == "explicit-human-authority-boundary"


def test_explicit_security_risk_sets_floor_without_asking_laya():
    provider = RecordingProvider()
    work = bundle(risks=("authentication trust boundary",))

    evaluation = advise_execution(work, provider=provider)

    assert evaluation.result.answers["security_review"].value == "required"
    assert evaluation.result.answers["change_risk"].value == "moderate"
    assert evaluation.result.answers["validation_focus"].value == "security"
    assert "security_review" not in provider.question_ids
    assert "change_risk" not in provider.question_ids
    assert "validation_focus" not in provider.question_ids


def test_operations_gap_resolves_validation_focus_only():
    provider = RecordingProvider()
    work = bundle(stage="operations", governance={"missing_evidence": ("deployment",)})

    evaluation = advise_execution(work, provider=provider)

    assert evaluation.result.answers["validation_focus"].value == "operations"
    assert "validation_focus" not in provider.question_ids
    assert "reasoning_tier" in provider.question_ids


def test_threshold_policy_is_validated_and_overrideable():
    assert threshold_for("validation_focus") < threshold_for("security_review")
    assert threshold_for("validation_focus", {"validation_focus": 0.7}) == 0.7

    try:
        threshold_for("security_review", {"security_review": 2.0})
    except ValueError as error:
        assert "invalid confidence threshold" in str(error)
    else:
        raise AssertionError("invalid threshold must fail closed")


def test_question_thresholds_can_escalate_security_without_escalating_focus():
    provider = RecordingProvider(confidence=0.85)
    evaluation = advise_execution(
        bundle(),
        provider=provider,
        confidence_thresholds={
            "security_review": 0.95,
            "reasoning_tier": 0.90,
            "change_risk": 0.90,
            "validation_focus": 0.80,
            "planner_needed": 0.90,
        },
    )

    assert "security_review" in evaluation.escalated
    assert "validation_focus" in evaluation.accepted
