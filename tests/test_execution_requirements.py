import json

from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_decisions import EXECUTION_QUESTIONS
from agora_ai_sdlc.execution_requirements import REQUIREMENTS_SCHEMA, requirements_for

DEFAULTS = {
    "reasoning_tier": "local",
    "security_review": "normal",
    "change_risk": "low",
    "validation_focus": "functional",
    "llm_needed": "yes",
}


def bundle(stage="construction", next_action="inspect-next", risks=(), human=False):
    return ExecutionBundle(
        schema="s", swarm="s", work="w", stage=stage, next_action=next_action, branch=None, base_branch=None,
        head=None, objective="o", acceptance_criteria=(), changed_paths=(), dirty_paths=(), related_paths=(),
        languages=(), build_systems=(), verification_commands=(), risks=tuple(risks),
        governance={"human_approval_required": human}, deterministic_inception_path=None,
    )  # fmt: skip


class Provider:
    name = "laya"

    def __init__(self, values=None, confidence=0.99, per=None, model="ckpt-1"):
        self.values = {**DEFAULTS, **(values or {})}
        self.confidence = confidence
        self.per = per or {}
        self.model = model

    def decide(self, state, questions):
        answers = {
            q.id: DecisionAnswer(q.id, "choice", self.values[q.id], self.per.get(q.id, self.confidence))
            for q in questions
        }
        return DecisionResult(self.name, answers, model=self.model)


def test_no_advisor_yields_safe_deterministic_requirements():
    req = requirements_for(bundle())
    assert req.to_dict()["schema"] == REQUIREMENTS_SCHEMA
    assert req.required_capabilities == ("workspace.read", "workspace.write", "shell.execute")
    assert req.advisory["provider"] is None and req.executable_by_agent


def test_local_tier_with_write_action_still_requires_write_capability():
    req = requirements_for(bundle(), Provider({"reasoning_tier": "local"}))
    assert req.reasoning_tier == "local"
    assert "workspace.write" in req.required_capabilities
    assert req.advisory["accepted"] == sorted(q.id for q in EXECUTION_QUESTIONS)


def test_byte_stable_and_provenance_only_model():
    assert requirements_for(bundle(), Provider()).to_json() == requirements_for(bundle(), Provider()).to_json()
    req = requirements_for(bundle(), Provider(model="other-ckpt"))
    assert req.advisory["model"] == "other-ckpt"
    assert "runtime" not in json.dumps(req.to_dict()).replace("required_capabilities", "")


def test_mixed_accepted_and_escalated():
    req = requirements_for(
        bundle(), Provider({"change_risk": "high", "security_review": "required"}, per={"change_risk": 0.3})
    )
    assert "change_risk" in req.advisory["escalated"] and "security_review" in req.advisory["accepted"]
    assert req.risk == "low" and req.security_review == "required" and "security" in req.validation_focus


def test_security_escalated_does_not_apply():
    req = requirements_for(bundle(), Provider({"security_review": "required"}, confidence=0.1))
    assert req.security_review == "normal" and req.advisory["accepted"] == []


def test_laya_cannot_lower_deterministic_risk_or_capabilities():
    req = requirements_for(
        bundle(risks=["security-sensitive"]), Provider({"change_risk": "low", "reasoning_tier": "local"})
    )
    assert req.risk == "moderate"
    assert set(req.required_capabilities) >= {"workspace.read", "workspace.write", "shell.execute"}


def test_human_tier_is_non_executable_authority_requirement():
    req = requirements_for(bundle(), Provider({"reasoning_tier": "human"}))
    assert req.reasoning_tier == "human" and req.human_authority_required
    assert req.required_capabilities == () and not req.executable_by_agent
    deterministic = requirements_for(bundle(next_action="human-approval", human=True))
    assert deterministic.activity_class == "human.authority" and not deterministic.executable_by_agent


def test_invalid_provider_shape_and_values_fail_open_to_deterministic():
    class Broken:
        name = "laya"

        def decide(self, state, questions):
            return DecisionResult("laya", {})

    class Raises:
        name = "laya"

        def decide(self, state, questions):
            raise RuntimeError("boom")

    baseline = requirements_for(bundle())
    for provider in (Broken(), Raises()):
        req = requirements_for(bundle(), provider)
        assert req.required_capabilities == baseline.required_capabilities and "error" in req.advisory
    weird = requirements_for(bundle(), Provider({"reasoning_tier": "ollama", "change_risk": "nuclear"}))
    assert weird.reasoning_tier == "local" and weird.risk == "low"


def test_independent_review_adds_isolated_reviewer_and_no_approval_in_output():
    req = requirements_for(bundle(), independent_review_required=True)
    assert "isolated_reviewer" in req.required_capabilities
    assert "approv" not in json.dumps(req.to_dict()).replace("human_authority_required", "")


def test_questions_carry_no_provider_names():
    text = json.dumps([q.as_laya() for q in EXECUTION_QUESTIONS]).lower()
    assert not any(name in text for name in ("ollama", "claude", "codex", "opencode", "anthropic", "openai"))


def test_confident_laya_no_projects_llm_need_without_changing_authority():
    req = requirements_for(bundle(), Provider({"llm_needed": "no"}))
    assert req.llm_needed == "no"
    assert req.executable_by_agent
    assert req.required_capabilities == ("workspace.read", "workspace.write", "shell.execute")


def test_uncertain_laya_no_fails_open_to_generative_need():
    req = requirements_for(bundle(), Provider({"llm_needed": "no"}, per={"llm_needed": 0.2}))
    assert req.llm_needed == "yes"
    assert "llm_needed" in req.advisory["escalated"]


def test_human_authority_never_requires_generative_executor():
    req = requirements_for(bundle(next_action="human-approval", human=True), Provider())
    assert req.llm_needed == "no"
    assert req.human_authority_required
