import json
from pathlib import Path

import pytest

PACK = Path(__file__).parent.parent / "registry" / "methods" / "ai-sdlc"


def front(path: Path) -> dict:
    lines = path.read_text().split("\n")
    out = {}
    for line in lines[1 : lines.index("---", 1)]:
        key, _, value = line.partition(":")
        try:
            out[key.strip()] = json.loads(value.strip())
        except ValueError:
            out[key.strip()] = value.strip()
    return out


ROLES = {p.stem: front(p) for p in (PACK / "roles").glob("*.md")}
GATES = {p.stem: front(p) for p in (PACK / "gates").glob("*.md")}
TRANSITIONS = [front(p) for p in sorted((PACK / "transitions").glob("*.md"))]
METHOD = front(PACK / "METHOD.md")
EXPECTED = {
    "product-owner", "domain-expert", "architect", "builder", "quality-reviewer",
    "security-reviewer", "operator", "ai-orchestrator", "governance-owner",
}  # fmt: skip


def can(role: str, action: str) -> bool:
    return action in ROLES[role]["allowed-actions"]


def test_role_set_is_exact_and_ids_match_files():
    assert set(ROLES) == EXPECTED
    assert all(r["id"] == name for name, r in ROLES.items())


def test_required_roles_exist():
    assert set(METHOD["required-roles"]) <= set(ROLES)


def test_every_transition_role_can_transition():
    for t in TRANSITIONS:
        assert t["roles"], t
        for role in t["roles"]:
            assert can(role, "work.transition"), (role, t["from"], t["to"])


def test_every_gate_approval_role_can_approve():
    for gate in GATES.values():
        for role in gate["required-approval-roles"]:
            assert can(role, "approval.add"), (role, gate["id"])


def test_every_criterion_stage_has_authorized_role():
    for stage, roles in METHOD["criterion-stage-roles"].items():
        assert roles and all(can(r, "criterion.satisfy") for r in roles), stage


def test_every_lifecycle_action_has_an_authorized_role():
    needed = {
        "work.create",
        "work.reopen",
        "work.transition",
        "approval.add",
        "criterion.satisfy",
        "artifact.add",
        "evidence.add",
        "work.clarify",
    }
    for action in needed:
        assert any(can(r, action) for r in ROLES), action


@pytest.mark.parametrize("role", sorted(EXPECTED))
def test_no_universal_authority(role):
    actions = ROLES[role]["allowed-actions"]
    assert "*" not in actions
    universal = {"work.transition", "approval.add", "criterion.satisfy", "gate.waive", "swarm.assign", "work.cancel"}
    assert not universal <= set(actions)


def test_only_governance_owner_can_waive_or_cancel():
    for action in ("gate.waive", "work.cancel"):
        assert [r for r in ROLES if can(r, action)] == ["governance-owner"]


def test_reopen_limited_to_product_owner_and_governance_owner():
    assert sorted(r for r in ROLES if can(r, "work.reopen")) == ["governance-owner", "product-owner"]


def test_governance_owner_is_human_only():
    assert ROLES["governance-owner"]["allowed-actor-kinds"] == ["human"]


def test_builder_can_never_approve_and_is_not_a_gate_approver():
    assert not can("builder", "approval.add")
    for gate in GATES.values():
        assert "builder" not in gate["required-approval-roles"]


@pytest.mark.parametrize("role", ["builder", "ai-orchestrator", "operator"])
def test_execution_roles_cannot_approve(role):
    assert not can(role, "approval.add")


def test_ai_orchestrator_has_no_governance_authority():
    for action in ("approval.add", "work.transition", "gate.waive", "criterion.satisfy"):
        assert not can("ai-orchestrator", action)
    assert "human" not in ROLES["ai-orchestrator"]["allowed-actor-kinds"]


def test_domain_expert_is_advisory():
    for action in ("work.transition", "approval.add", "criterion.satisfy"):
        assert not can("domain-expert", action)


@pytest.mark.parametrize("kind", ["human", "ai-agent", "swarm"])
def test_each_actor_kind_can_hold_a_role(kind):
    assert [r for r, d in ROLES.items() if kind in d["allowed-actor-kinds"]]


def test_delegating_roles_document_human_accountability():
    for role, data in ROLES.items():
        if "ai-agent" in data["allowed-actor-kinds"]:
            body = (PACK / "roles" / f"{role}.md").read_text().lower()
            assert "accountab" in body, role


def test_starter_small_team_combination_covers_required_roles():
    # A single human plus one AI can cover every required role only if actor kinds allow it.
    for role in METHOD["required-roles"]:
        kinds = ROLES[role]["allowed-actor-kinds"]
        assert "human" in kinds and "ai-agent" in kinds, role


def test_usage_recording_is_limited_to_the_roles_that_run_executions_and_never_approves():
    assert sorted(r for r in ROLES if can(r, "usage.add")) == ["builder", "operator"]
    for role in ("builder", "operator"):
        assert not can(role, "approval.add") and not can(role, "gate.waive")
