from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.artifacts import check_traceability, parse_artifact
from agora_ai_sdlc.change_management import (
    ChangeManagementError,
    assert_approved,
    parse_change_plan,
    parse_change_request,
    parse_configuration_delta,
    summary,
    validate_chain,
)

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "change-management"
TRACE = ROOT / "tests" / "fixtures" / "trace"
PLANS = ROOT / "tests" / "fixtures" / "plans"


def text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def mutate(name: str, fn) -> str:
    lines = text(name).splitlines()
    end = lines.index("---", 1)
    front = yaml.safe_load("\n".join(lines[1:end]))
    fn(front)
    return "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n" + "\n".join(lines[end + 1 :])


def test_valid_change_chain_is_approved_and_release_traceable():
    request = parse_change_request(text("change-request.md"))
    plan = parse_change_plan(text("change-plan.md"))
    delta = parse_configuration_delta(text("configuration-delta.md"))
    chain = validate_chain(request, plan, delta)

    assert summary(chain) == {
        "change_request": "CRQ-001",
        "change_plan": "CHP-001",
        "configuration_delta": "CFD-001",
        "risk": "medium",
        "release_evidence": ["evidence:release/payments-2026.09.21"],
        "rollback_linkage": ["repo://ops/rollback/recurring-payments.md"],
        "change_count": 1,
        "approved": True,
    }


def test_change_chain_joins_generic_artifact_traceability():
    artifacts = [
        parse_artifact((TRACE / "intent.md").read_text(encoding="utf-8")),
        parse_artifact((TRACE / "unit.md").read_text(encoding="utf-8")),
        parse_artifact((PLANS / "level1.md").read_text(encoding="utf-8")),
        parse_artifact(text("change-request.md")),
        parse_artifact(text("change-plan.md")),
        parse_artifact(text("configuration-delta.md")),
    ]
    check_traceability(artifacts)


def test_stale_or_unapproved_change_plan_blocks_chain():
    stale = mutate("change-plan.md", lambda front: front.update(revision=3))
    with pytest.raises(ChangeManagementError) as exc:
        parse_change_plan(stale)
    assert exc.value.code == "change.approval_stale"

    pending = mutate(
        "change-plan.md",
        lambda front: front.update({"approval-state": "pending", "approved-by": None, "approved-revision": None}),
    )
    plan = parse_change_plan(pending)
    with pytest.raises(ChangeManagementError) as exc:
        assert_approved(plan)
    assert exc.value.code == "change.not_approved"


def test_configuration_delta_requires_release_and_rollback_links():
    with pytest.raises(ChangeManagementError) as exc:
        parse_configuration_delta(mutate("configuration-delta.md", lambda front: front.update({"release-evidence": []})))
    assert exc.value.code == "change.type"

    with pytest.raises(ChangeManagementError) as exc:
        parse_configuration_delta(mutate("configuration-delta.md", lambda front: front.update({"rollback-linkage": []})))
    assert exc.value.code == "change.type"


@pytest.mark.parametrize("field", ["token", "password", "api_key", "authorization"])
def test_configuration_delta_rejects_secret_keys_without_echoing_values(field):
    secret = "sensitive-value-do-not-echo"

    def fn(front):
        front["changes"][0] = {"key": field, "before": "none", "after": secret, "resource": "config"}

    with pytest.raises(ChangeManagementError) as exc:
        parse_configuration_delta(mutate("configuration-delta.md", fn))
    assert exc.value.code == "change.secret_key"
    assert secret not in str(exc.value)


def test_configuration_delta_rejects_secret_like_values_and_credential_query_refs():
    secret = "token=super-sensitive"

    def value_fn(front):
        front["changes"][0]["after"] = secret

    with pytest.raises(ChangeManagementError) as exc:
        parse_configuration_delta(mutate("configuration-delta.md", value_fn))
    assert exc.value.code == "change.secret_value"
    assert secret not in str(exc.value)

    with pytest.raises(ChangeManagementError) as exc:
        parse_configuration_delta(
            mutate(
                "configuration-delta.md",
                lambda front: front.update({"release-evidence": ["evidence:release?token=super-sensitive"]}),
            )
        )
    assert exc.value.code == "change.reference_secret"
    assert "super-sensitive" not in str(exc.value)


def test_chain_identity_mismatch_fails_closed():
    request = parse_change_request(text("change-request.md"))
    plan = parse_change_plan(text("change-plan.md"))
    delta = parse_configuration_delta(text("configuration-delta.md"))

    other_request = parse_change_request(
        mutate("change-request.md", lambda front: front.update({"id": "CRQ-002"}))
    )
    with pytest.raises(ChangeManagementError) as exc:
        validate_chain(other_request, plan, delta)
    assert exc.value.code == "change.chain_request"

    other_delta = parse_configuration_delta(
        mutate(
            "configuration-delta.md",
            lambda front: front.update({"change-plan": "CHP-002", "traces-to": ["CHP-002"]}),
        )
    )
    with pytest.raises(ChangeManagementError) as exc:
        validate_chain(request, plan, other_delta)
    assert exc.value.code == "change.chain_plan"
