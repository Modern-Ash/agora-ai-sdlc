from agora_ai_sdlc.context_relevance import (
    RelevanceCache,
    RelevanceInput,
    classify_relevance,
)
from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionQuestion, DecisionResult

QUESTION = DecisionQuestion(
    id="relevance",
    type="choice",
    instructions="Classify bounded relevance.",
    criteria={"required": "needed", "useful": "helpful", "irrelevant": "not needed"},
)


class BatchProvider:
    name = "laya"
    model = "checkpoint-a"

    def __init__(self):
        self.batch_calls = 0
        self.items = 0

    def decide_many(self, batch):
        self.batch_calls += 1
        self.items += len(batch)
        return tuple(
            DecisionResult(
                provider=self.name,
                model=self.model,
                answers={
                    "relevance": DecisionAnswer(
                        "relevance",
                        "choice",
                        "required" if state["candidate"]["content"].startswith("keep") else "irrelevant",
                        0.99,
                    )
                },
                latency_ms=2.0,
            )
            for state, _ in batch
        )


def item(name: str, content: str, objective: str = "ship") -> RelevanceInput:
    return RelevanceInput(
        id=name,
        content=content,
        state={
            "objective": objective,
            "candidate": {"id": name, "content": content},
        },
    )


def test_cache_reuses_unchanged_candidates_without_calling_laya_again():
    provider = BatchProvider()
    cache = RelevanceCache()
    inputs = (item("a", "keep a"), item("b", "drop b"))

    first = classify_relevance(inputs, provider=provider, question=QUESTION, confidence_threshold=0.9, cache=cache)
    second = classify_relevance(inputs, provider=provider, question=QUESTION, confidence_threshold=0.9, cache=cache)

    assert provider.batch_calls == 1
    assert provider.items == 2
    assert cache.hits == 2 and cache.misses == 2
    assert all(not result.reused for result in first.values())
    assert all(result.reused for result in second.values())


def test_changed_content_invalidates_only_changed_candidate():
    provider = BatchProvider()
    cache = RelevanceCache()
    classify_relevance(
        (item("a", "keep a"), item("b", "drop b")),
        provider=provider,
        question=QUESTION,
        confidence_threshold=0.9,
        cache=cache,
    )

    results = classify_relevance(
        (item("a", "keep a"), item("b", "keep changed")),
        provider=provider,
        question=QUESTION,
        confidence_threshold=0.9,
        cache=cache,
    )

    assert provider.batch_calls == 2
    assert provider.items == 3
    assert results["a"].reused is True
    assert results["b"].reused is False
    assert results["b"].label == "required"


def test_objective_or_model_change_invalidates_relevance():
    provider = BatchProvider()
    cache = RelevanceCache()
    classify_relevance(
        (item("a", "keep a"),),
        provider=provider,
        question=QUESTION,
        confidence_threshold=0.9,
        cache=cache,
    )
    classify_relevance(
        (item("a", "keep a", objective="different"),),
        provider=provider,
        question=QUESTION,
        confidence_threshold=0.9,
        cache=cache,
    )
    provider.model = "checkpoint-b"
    classify_relevance(
        (item("a", "keep a", objective="different"),),
        provider=provider,
        question=QUESTION,
        confidence_threshold=0.9,
        cache=cache,
    )

    assert provider.items == 3


def test_low_confidence_is_cached_as_escalated_and_still_fails_open_upstream():
    class Low(BatchProvider):
        def decide_many(self, batch):
            self.batch_calls += 1
            self.items += len(batch)
            return tuple(
                DecisionResult(
                    provider=self.name,
                    model=self.model,
                    answers={"relevance": DecisionAnswer("relevance", "choice", "irrelevant", 0.4)},
                )
                for _ in batch
            )

    provider = Low()
    result = classify_relevance(
        (item("a", "drop a"),),
        provider=provider,
        question=QUESTION,
        confidence_threshold=0.9,
    )

    assert result["a"].escalated is True
