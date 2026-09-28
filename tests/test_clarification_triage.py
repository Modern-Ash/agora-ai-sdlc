from agora_ai_sdlc.clarification_triage import triage_clarifications
from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult
from agora_ai_sdlc.deterministic_inception import IssueFacts


def issue() -> IssueFacts:
    return IssueFacts(
        title="Add discount",
        objective="Add percentage discount calculation",
        requirements=("Calculate a percentage discount.",),
        acceptance_criteria=("100 with 10 percent returns 90.",),
        dependencies=(),
        constraints=(),
        semantic_gaps=("acceptance criteria or requirements are not explicit",),
    )


class Provider:
    name = "laya"
    model = "test"

    def __init__(self, mapping, confidence=0.99):
        self.mapping = mapping
        self.confidence = confidence
        self.calls = 0

    def decide_many(self, batch):
        self.calls += 1
        return tuple(
            DecisionResult(
                provider=self.name,
                model=self.model,
                answers={
                    "material_gap": DecisionAnswer(
                        "material_gap",
                        "choice",
                        self.mapping[state["candidate_gap"]],
                        self.confidence,
                    )
                },
            )
            for state, _ in batch
        )


def test_no_candidates_need_no_laya_call():
    provider = Provider({})
    result = triage_clarifications(issue(), (), provider=provider)

    assert result.gaps == ()
    assert provider.calls == 0


def test_high_confidence_no_gap_removes_heuristic_candidate():
    source = "acceptance criteria or requirements are not explicit"
    provider = Provider({source: "none"})

    result = triage_clarifications(issue(), (source,), provider=provider)

    assert result.material_gaps == ()
    assert result.unresolved == ()
    assert provider.calls == 1


def test_real_gap_returns_only_material_category():
    gaps = ("expected behavior unclear", "persistence unclear")
    provider = Provider(
        {
            "expected behavior unclear": "expected-behavior",
            "persistence unclear": "persistence",
        }
    )

    result = triage_clarifications(issue(), gaps, provider=provider)

    assert tuple(gap.category for gap in result.material_gaps) == (
        "expected-behavior",
        "persistence",
    )
    assert provider.calls == 1


def test_low_confidence_fails_open_even_when_laya_says_no_gap():
    source = "acceptance criteria or requirements are not explicit"
    provider = Provider({source: "none"}, confidence=0.4)

    result = triage_clarifications(issue(), (source,), provider=provider)

    assert result.material_gaps == ()
    assert tuple(gap.source for gap in result.unresolved) == (source,)
