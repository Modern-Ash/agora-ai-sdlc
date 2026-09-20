import copy
import json
from pathlib import Path

import pytest
from agora.filesystem import packs_root
from agora.tools import load_tool_contract

from agora_ai_sdlc.github_delivery import (
    GitHubDeliveryError,
    authorize_operation,
    ingest_snapshot,
    load_profile,
    normalize_delivery,
)

FIXTURE = Path(__file__).parents[1] / "samples" / "github-delivery" / "fixture.json"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_profile_operations_match_installed_core_adapter_contracts():
    profile = load_profile()
    assert profile["default_mode"] == "read-only"
    assert set(profile["adapters"]) == {"github-issues", "github-pull-requests", "github-actions"}
    for expected in profile["operations"].values():
        contract = load_tool_contract(packs_root() / "adapters" / "cli" / expected["adapter"])
        operation = contract.operations[expected["operation"]]
        assert operation.capability == expected["capability"]
        assert operation.risk == expected["risk"]


def test_read_only_is_default_and_every_write_needs_grant_and_confirmation():
    assert authorize_operation("issue-view") == {
        "allowed": True,
        "mode": "read-only",
        "adapter": "github-issues",
        "operation": "view",
        "capability": "issue.read",
        "risk": "read",
        "blockers": [],
    }
    denied = authorize_operation("issue-create")
    assert not denied["allowed"]
    assert {item["code"] for item in denied["blockers"]} == {
        "github.mode.denied",
        "github.capability.missing",
        "github.confirmation.required",
    }
    assert not authorize_operation("issue-create", mode="delivery-write", granted_capabilities=("issue.write",))[
        "allowed"
    ]
    assert not authorize_operation("issue-create", mode="delivery-write", confirmed=True)["allowed"]
    assert authorize_operation(
        "issue-create",
        mode="delivery-write",
        granted_capabilities=("issue.write",),
        confirmed=True,
    )["allowed"]


def test_all_declared_writes_require_their_mode_capability_and_confirmation():
    profile = load_profile()
    for name, operation in profile["operations"].items():
        if operation["risk"] == "read":
            continue
        capability = operation["capability"]
        mode = "merge-write" if capability == "review.merge" else "delivery-write"
        assert not authorize_operation(name)["allowed"]
        assert not authorize_operation(name, mode=mode, granted_capabilities=(capability,))["allowed"]
        assert not authorize_operation(name, mode=mode, confirmed=True)["allowed"]
        assert authorize_operation(
            name,
            mode=mode,
            granted_capabilities=(capability,),
            confirmed=True,
        )["allowed"]


def test_normalized_delivery_is_commit_bound_and_idempotent():
    snapshot = normalize_delivery(**fixture())
    assert snapshot["allowed"]
    assert snapshot["verification"]["revision"] == fixture()["expected_revision"]
    assert snapshot["evidence_references"][-1].endswith(f"#commit={fixture()['expected_revision']}")
    observations, created = ingest_snapshot((), snapshot)
    repeated, repeated_created = ingest_snapshot(observations, copy.deepcopy(snapshot))
    assert created and not repeated_created and repeated == observations


def test_stale_commit_cannot_satisfy_verification():
    data = fixture()
    data["check_run"]["headSha"] = "b" * 40
    snapshot = normalize_delivery(**data)
    assert not snapshot["allowed"]
    assert "github.check.stale" in {item["code"] for item in snapshot["blockers"]}


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda data: data["check_run"].update(conclusion="failure"), "github.check.unsuccessful"),
        (lambda data: data["check_run"].update(status="in_progress"), "github.check.pending"),
        (lambda data: data["pull_request"].update(reviewDecision="CHANGES_REQUESTED"), "github.review.unapproved"),
        (lambda data: data["pull_request"].update(statusCheckRollup=[]), "github.check.unbound"),
        (lambda data: data["check_run"].update(headBranch="other"), "github.check.branch"),
        (lambda data: data["pull_request"].update(state="CLOSED"), "github.pr.closed"),
        (lambda data: data["pull_request"].update(isDraft=True), "github.pr.draft"),
    ],
)
def test_incomplete_or_mismatched_delivery_fails_closed(mutation, code):
    data = fixture()
    mutation(data)
    snapshot = normalize_delivery(**data)
    assert not snapshot["allowed"]
    assert code in {item["code"] for item in snapshot["blockers"]}


def test_malformed_provider_fact_is_distinct_from_policy_denial():
    data = fixture()
    del data["issue"]["url"]
    with pytest.raises(GitHubDeliveryError) as error:
        normalize_delivery(**data)
    assert error.value.code == "github.fact.missing"
    assert authorize_operation("issue-create")["blockers"][0]["code"] == "github.mode.denied"


def test_external_reference_must_match_project_and_origin():
    data = fixture()
    data["pull_request"]["url"] = "https://github.com/other/project/pull/56"
    with pytest.raises(GitHubDeliveryError) as error:
        normalize_delivery(**data)
    assert error.value.code == "github.fact.project"


def test_unknown_mode_and_operation_are_rejected():
    with pytest.raises(GitHubDeliveryError, match="unknown permission mode"):
        authorize_operation("issue-view", mode="owner")
    with pytest.raises(GitHubDeliveryError, match="unknown operation"):
        authorize_operation("repository-delete")
