import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from support import runtime_scenarios as sc
from test_context_selection import RelevanceProvider, graph

from agora_ai_sdlc.context_selection import select_context_with_laya
from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult
from agora_ai_sdlc.execution_decisions import EXECUTION_QUESTIONS
from agora_ai_sdlc.execution_envelope import build_envelope
from agora_ai_sdlc.execution_requirements import requirements_for


class Advisor:
    name = "laya"

    def __init__(self, values, confidence=0.99):
        self.values, self.confidence = values, confidence

    def decide(self, state, questions):
        defaults = {
            "reasoning_tier": "local",
            "security_review": "normal",
            "change_risk": "low",
            "validation_focus": "functional",
        }
        merged = {**defaults, **self.values}
        answers = {q.id: DecisionAnswer(q.id, "choice", merged[q.id], self.confidence) for q in questions}
        return DecisionResult("laya", answers, model="ckpt")


def envelope_for(req):
    return build_envelope(sc.snapshot(), req, sc.BINDINGS["claude"], sc.bundle(), actor_id=sc.ACTOR).to_dict()


def test_laya_installed_or_unavailable_does_not_change_authority():
    without = requirements_for(sc.bundle())
    with_laya = requirements_for(sc.bundle(), Advisor({"change_risk": "high", "security_review": "required"}))
    for key in ("activity_class", "human_authority_required", "executable_by_agent"):
        assert without.to_dict()[key] == with_laya.to_dict()[key]
    assert set(without.required_capabilities) <= set(with_laya.required_capabilities)
    a, b = envelope_for(without), envelope_for(with_laya)
    assert a["authority"] == b["authority"] and a["next_transition"] == b["next_transition"] and a["work"] == b["work"]


def test_accepted_signals_only_touch_advisory_requirement_fields():
    base = requirements_for(sc.bundle()).to_dict()
    tuned = requirements_for(sc.bundle(), Advisor({"change_risk": "high", "validation_focus": "performance"})).to_dict()
    changed = {key for key in base if base[key] != tuned[key]}
    assert changed <= {"risk", "validation_focus", "advisory"}


def test_low_confidence_fails_open_and_provider_names_are_never_answers():
    base = requirements_for(sc.bundle())
    low = requirements_for(sc.bundle(), Advisor({"change_risk": "high", "reasoning_tier": "frontier"}, confidence=0.2))
    assert (low.risk, low.reasoning_tier) == (base.risk, base.reasoning_tier)
    assert low.advisory["accepted"] == [] and len(low.advisory["escalated"]) == len(EXECUTION_QUESTIONS)
    named = requirements_for(sc.bundle(), Advisor({"reasoning_tier": "ollama", "validation_focus": "claude"}))
    assert named.reasoning_tier == "local" and named.validation_focus == ("functional",)
    text = json.dumps([q.as_laya() for q in EXECUTION_QUESTIONS]).lower()
    assert not any(name in text for name in ("ollama", "claude", "codex", "opencode"))


def test_context_pruning_is_selection_only_and_cannot_invent_context():
    selection = select_context_with_laya(graph(), "REQ-001", provider=RelevanceProvider(), confidence_threshold=0.9)
    candidate_ids = {item.id for item in selection.candidate.items}
    assert {item.id for item in selection.selected.items} <= candidate_ids
    assert set(selection.selected.text) <= set(selection.candidate.text)
    assert selection.selected.total_tokens <= selection.candidate.total_tokens
