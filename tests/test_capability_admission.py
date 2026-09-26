import json

import pytest

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_requirements import ExecutionRequirements, requirements_for
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding
from agora_ai_sdlc.runtime_selection import Budget, Candidate, Route, select_runtime

ALLOW = {"allowed": True, "blockers": []}
DENY = {"allowed": False, "blockers": [{"code": "data.blocked"}]}


def bundle():
    return ExecutionBundle(
        schema="s", swarm="s", work="w", stage="construction", next_action="inspect-next", branch=None,
        base_branch=None, head=None, objective="o", acceptance_criteria=(), changed_paths=(), dirty_paths=(),
        related_paths=(), languages=(), build_systems=(), verification_commands=(), risks=(),
        governance={}, deterministic_inception_path=None,
    )  # fmt: skip


REQ = requirements_for(bundle())
OPENCODE = RuntimeBinding(AgentRuntimeRef("opencode", "opencode"), ModelRuntimeRef("ollama", "ollama", "qwen"))
CLAUDE = RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef("anthropic", "anthropic", "m"))
OLLAMA = ModelRuntimeRef("ollama", "ollama", "qwen")


def cand(runtime, data=ALLOW, usage=None):
    return Candidate(runtime, usage or {}, data, ALLOW)


def route(*runtimes, fallback=("quota", "runtime-unavailable", "budget-exhausted", "capability-mismatch")):
    return Route("build", tuple(cand(r) for r in runtimes), allowed_fallback_signals=fallback)


def found(**states):
    def one(name, ok):
        return RuntimeDiscovery(name, name, name, ok, "/x" if ok else None, ok, "1", True, "responsive" if ok else None)

    return {name: one(name, ok) for name, ok in states.items()}


def test_first_candidate_admissible():
    result = select_runtime(route(OPENCODE, CLAUDE), requirements=REQ, availability=found(opencode=True, ollama=True))
    assert result["allowed"] and result["selected"]["id"] == "opencode" and not result["fallback"]["used"]


def test_first_candidate_missing_capability_is_machine_readable():
    needy = ExecutionRequirements(**{**REQ.__dict__, "required_capabilities": ("workspace.read", "isolated_reviewer")})
    result = select_runtime(route(CLAUDE), requirements=needy, availability=found(claude=True, anthropic=True))
    assert not result["allowed"]
    assert result["considered"][0]["missing_capabilities"] == ("isolated_reviewer",)
    assert "runtime.capability_missing" in result["considered"][0]["blockers"]


def test_model_runtime_alone_cannot_execute_and_opencode_composition_can():
    result = select_runtime(route(OLLAMA), requirements=REQ, availability=found(ollama=True))
    assert not result["allowed"] and result["considered"][0]["blockers"] == ("runtime.agent_required",)
    assert select_runtime(route(OPENCODE), requirements=REQ, availability=found(opencode=True, ollama=True))["allowed"]


def test_legacy_ollama_as_agent_is_agent_required():
    from agora_ai_sdlc.runtime_selection import RuntimeRef

    result = select_runtime(route(RuntimeRef("ollama", "generic", "ollama", "q")), requirements=REQ)
    assert result["considered"][0]["blockers"] == ("runtime.agent_required",)


def test_fallback_to_later_candidate_only_when_policy_permits():
    needy = ExecutionRequirements(
        **{**REQ.__dict__, "required_capabilities": ("workspace.read", "structured_output")}
    )
    avail = found(opencode=True, ollama=True, claude=True, anthropic=True)
    allowed = select_runtime(route(OPENCODE, CLAUDE), requirements=needy, availability=avail)
    assert allowed["selected"]["id"] == "claude" and allowed["fallback"] == {
        "used": True,
        "reason": "capability-mismatch",
    }
    strict = select_runtime(route(OPENCODE, CLAUDE, fallback=("quota",)), requirements=needy, availability=avail)
    assert not strict["allowed"] and strict["blockers"][0]["code"] == "fallback.unauthorized_signal"


def test_model_service_unavailable_and_integration_unavailable():
    result = select_runtime(route(OPENCODE), requirements=REQ, availability=found(opencode=True, ollama=False))
    assert result["considered"][0]["blockers"] == ("runtime.model_unavailable",)
    result = select_runtime(route(OPENCODE), requirements=REQ, availability=found(ollama=True))
    assert result["considered"][0]["blockers"] == ("runtime.integration_unavailable",)


def test_local_tier_needs_model_binding():
    bare = RuntimeBinding(AgentRuntimeRef("claude", "claude-code"))
    result = select_runtime(route(bare), requirements=REQ)
    assert "runtime.model_binding_missing" in result["considered"][0]["blockers"]


def test_budget_and_data_policy_keep_existing_behavior():
    budget = Budget("s", {"tokens": 10}, {"tokens": 10})
    exhausted = Route(
        "build",
        (Candidate(OPENCODE, {"tokens": 1}, ALLOW, ALLOW),),
    )
    result = select_runtime(exhausted, budgets=(budget,), requirements=REQ)
    assert "budget.exhausted" in result["considered"][0]["blockers"]
    blocked = select_runtime(Route("build", (Candidate(OPENCODE, {}, DENY, ALLOW), cand(CLAUDE))), requirements=REQ)
    assert not blocked["allowed"] and blocked["considered"][0]["blockers"] == ("runtime.data_policy",)


def test_ordinary_failure_never_hops():
    result = select_runtime(route(OPENCODE, CLAUDE), signal="ordinary-failure", requirements=REQ)
    assert not result["allowed"] and result["blockers"][0]["code"] == "fallback.ordinary_failure"


def test_unknown_capability_fails_closed():
    bad = ExecutionRequirements(**{**REQ.__dict__, "required_capabilities": ("telepathy",)})
    with pytest.raises(ValueError, match="unknown capability"):
        select_runtime(route(OPENCODE), requirements=bad)


def test_human_authority_is_terminal():
    human = ExecutionRequirements(**{**REQ.__dict__, "human_authority_required": True, "required_capabilities": ()})
    result = select_runtime(route(OPENCODE), requirements=human)
    assert result["blockers"][0]["code"] == "runtime.human_authority_required"


def test_selection_is_byte_stable():
    args = {"requirements": REQ, "availability": found(opencode=True, ollama=True)}
    first = json.dumps(select_runtime(route(OPENCODE, CLAUDE), **args), sort_keys=True)
    assert first == json.dumps(select_runtime(route(OPENCODE, CLAUDE), **args), sort_keys=True)


def test_no_requirements_keeps_v1_result_shape():
    result = select_runtime(route(OPENCODE))
    assert "missing_capabilities" not in result["considered"][0]
