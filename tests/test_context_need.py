from agora_ai_sdlc.context_need import ContextNeedCache, decide_context_need
from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult


class Provider:
    name = "laya"
    model = "typed"

    def __init__(self, value="bounded", confidence=0.99):
        self.value = value
        self.confidence = confidence
        self.calls = 0

    def decide(self, state, questions):
        self.calls += 1
        question = questions[0]
        return DecisionResult(
            self.name,
            {
                question.id: DecisionAnswer(
                    question.id,
                    question.type,
                    self.value,
                    self.confidence,
                )
            },
            model=self.model,
        )


def test_system0_skips_laya_for_no_context_action():
    provider = Provider()
    result = decide_context_need(
        action="human-approval",
        objective="approve",
        acceptance_criteria=(),
        provider=provider,
    )
    assert result.value == "none"
    assert result.source == "system0"
    assert provider.calls == 0


def test_confident_laya_can_choose_none_or_bounded():
    none = decide_context_need(
        action="explain",
        objective="explain result",
        acceptance_criteria=(),
        provider=Provider("none"),
    )
    bounded = decide_context_need(
        action="implement",
        objective="change code",
        acceptance_criteria=("tests pass",),
        provider=Provider("bounded"),
    )
    assert none.value == "none" and not none.escalated
    assert bounded.value == "bounded" and not bounded.escalated


def test_low_confidence_none_fails_open_to_bounded():
    result = decide_context_need(
        action="implement",
        objective="change code",
        acceptance_criteria=(),
        provider=Provider("none", 0.2),
    )
    assert result.value == "bounded"
    assert result.escalated


def test_context_need_cache_reuses_unchanged_action_snapshot():
    provider = Provider("bounded")
    cache = ContextNeedCache()
    kwargs = {
        "action": "implement",
        "objective": "change code",
        "acceptance_criteria": ("tests pass",),
        "provider": provider,
        "cache": cache,
    }
    first = decide_context_need(**kwargs)
    second = decide_context_need(**kwargs)
    assert provider.calls == 1
    assert not first.reused and second.reused
    assert cache.hits == 1 and cache.misses == 1
