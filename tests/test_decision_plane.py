from types import SimpleNamespace

import pytest

from agora_ai_sdlc.decision_plane import (
    ConfidencePolicy,
    DecisionPlaneError,
    DecisionQuestion,
    evaluate_with_confidence,
)
from agora_ai_sdlc.laya_provider import LayaDecisionProvider


class FakeRouter:
    def __init__(self, confidence=0.96):
        self.confidence = confidence
        self.calls = []

    def predict(self, state, questions, model=None):
        self.calls.append((state, questions, model))
        return {
            "answers": {
                "route": {
                    "type": "choice",
                    "choice": "local",
                    "probabilities": {"local": self.confidence, "frontier": 1 - self.confidence},
                    "confidence": self.confidence,
                }
            },
            "routing": {"model": model or "typed-decisions", "reason": "test"},
        }


def question():
    return DecisionQuestion(
        id="route",
        type="choice",
        instructions="Choose a tier",
        criteria={"local": "bounded", "frontier": "complex"},
    )


def test_laya_provider_normalizes_choice_and_uses_typed_checkpoint():
    router = FakeRouter()
    provider = LayaDecisionProvider(router=router)
    result = provider.decide({"task": "rename field"}, (question(),))

    assert result.provider == "laya"
    assert result.model == "typed-decisions"
    assert result.answers["route"].value == "local"
    assert result.answers["route"].confidence == pytest.approx(0.96)
    assert router.calls[0][2] == "typed-decisions"


def test_confidence_policy_escalates_uncertain_answer():
    provider = LayaDecisionProvider(router=FakeRouter(confidence=0.61))
    evaluation = evaluate_with_confidence(
        provider,
        {"task": "ambiguous"},
        (question(),),
        policy=ConfidencePolicy(0.90),
    )

    assert evaluation.accepted == ()
    assert evaluation.escalated == ("route",)
    assert not evaluation.all_confident


def test_answer_set_must_match_questions():
    class BrokenProvider:
        name = "broken"

        def decide(self, state, questions):
            return SimpleNamespace(answers={}, provider="broken")

    with pytest.raises(DecisionPlaneError) as exc:
        evaluate_with_confidence(BrokenProvider(), {"x": 1}, (question(),))
    assert exc.value.code == "decision.answer_set"
