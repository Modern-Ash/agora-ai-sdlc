import copy
import json
from pathlib import Path

import pytest
from agora.filesystem import packs_root
from agora.tools import load_tool_contract

from agora_ai_sdlc.follow_on_delivery import (
    FollowOnDeliveryError,
    authorize_operation,
    load_profile,
    normalize_gitlab_delivery,
    normalize_work_item,
    reconcile_observation,
)

ROOT = Path(__file__).parents[1]
GITLAB_FIXTURE = ROOT / "samples" / "gitlab-delivery" / "fixture.json"
JIRA_FIXTURE = ROOT / "samples" / "jira-work-items" / "fixture.json"


def gitlab_fixture():
    return json.loads(GITLAB_FIXTURE.read_text(encoding="utf-8"))


def jira_fixture():
    return json.loads(JIRA_FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("provider", ["gitlab", "jira"])
def test_profile_operations_match_installed_core_adapter_contracts(provider):
    profile = load_profile(provider)
    assert profile["default_mode"] == "read-only"
    for expected in profile["operations"].values():
        contract = load_tool_contract(packs_root() / "adapters" / "cli" / expected["adapter"])
        operation = contract.operations[expected["operation"]]
        assert (operation.capability, operation.risk) == (expected["capability"], expected["risk"])


def test_profiles_reuse_github_neutral_capabilities():
    github = load_tool_contract(packs_root() / "adapters" / "cli" / "github-issues")
    neutral_issue_capabilities = {operation.capability for operation in github.operations.values()}
    assert {"issue.read", "issue.write", "issue.transition"} <= neutral_issue_capabilities
    for provider in ("gitlab", "jira"):
        profile_capabilities = {operation["capability"] for operation in load_profile(provider)["operations"].values()}
        assert {
            capability for capability in profile_capabilities if capability.startswith("issue.")
        } <= neutral_issue_capabilities


def test_jira_fixture_uses_only_bounded_view_fields_plus_observation_metadata():
    operation = load_tool_contract(packs_root() / "adapters" / "cli" / "jira").operations["view"]
    fields = operation.arguments[operation.arguments.index("--fields") + 1].split(",")
    fixture = jira_fixture()
    assert set(fixture["item"]["fields"]) <= set(fields)
    assert set(fixture["item"]) == {"key", "fields"}
    assert "observed_at" in fixture and "updated" not in fixture["item"]["fields"]
    assert normalize_work_item("jira", **fixture)["source"]["url"].endswith("/browse/AGORA-30")


def test_method_pack_does_not_branch_on_follow_on_provider_names():
    method_files = (ROOT / "registry" / "methods").rglob("*")
    text = "\n".join(path.read_text(encoding="utf-8").casefold() for path in method_files if path.is_file())
    assert "gitlab" not in text
    assert "jira" not in text


@pytest.mark.parametrize(
    ("provider", "read_operation", "write_operation", "mode", "capability"),
    [
        ("gitlab", "issue-view", "issue-comment", "delivery-write", "issue.write"),
        ("jira", "work-item-view", "work-item-transition", "work-write", "issue.transition"),
    ],
)
def test_read_only_default_and_writes_require_mode_grant_and_confirmation(
    provider, read_operation, write_operation, mode, capability
):
    assert authorize_operation(provider, read_operation)["allowed"]
    assert not authorize_operation(provider, write_operation)["allowed"]
    assert not authorize_operation(provider, write_operation, mode=mode, granted_capabilities=(capability,))["allowed"]
    assert not authorize_operation(provider, write_operation, mode=mode, confirmed=True)["allowed"]
    assert authorize_operation(
        provider,
        write_operation,
        mode=mode,
        granted_capabilities=(capability,),
        confirmed=True,
    )["allowed"]


@pytest.mark.parametrize("provider", ["gitlab", "jira"])
def test_every_declared_write_is_opt_in(provider):
    profile = load_profile(provider)
    for name, operation in profile["operations"].items():
        if operation["risk"] == "read":
            continue
        capability = operation["capability"]
        mode = next(name for name, value in profile["modes"].items() if capability in value["capabilities"])
        assert not authorize_operation(provider, name)["allowed"]
        assert authorize_operation(
            provider,
            name,
            mode=mode,
            granted_capabilities=(capability,),
            confirmed=True,
        )["allowed"]


@pytest.mark.parametrize(
    ("provider", "operation", "code"),
    [
        ("gitlab", "issue-create", "gitlab.operation.unsupported"),
        ("gitlab", "merge-request-merge", "gitlab.operation.unsupported"),
        ("jira", "review-approve", "jira.operation.unsupported"),
        ("jira", "repository-delete", "jira.operation.unknown"),
    ],
)
def test_unsupported_and_unknown_operations_fail_clearly(provider, operation, code):
    with pytest.raises(FollowOnDeliveryError) as error:
        authorize_operation(provider, operation)
    assert error.value.code == code


def test_gitlab_and_jira_fixtures_have_equivalent_normalized_outcomes():
    gitlab = gitlab_fixture()
    jira = jira_fixture()
    gitlab_item = normalize_work_item(
        "gitlab",
        scope=f"{gitlab['origin']}/{gitlab['project']}",
        observed_at=gitlab["observed_at"],
        item=gitlab["issue"],
    )
    jira_item = normalize_work_item("jira", **jira)
    assert gitlab_item["outcome"] == jira_item["outcome"] == {"state": "open", "terminal": False}
    assert gitlab_item["source"]["provider"] != jira_item["source"]["provider"]


def test_gitlab_delivery_is_commit_bound_and_retries_are_idempotent():
    snapshot = normalize_gitlab_delivery(**gitlab_fixture())
    assert snapshot["allowed"]
    assert snapshot["verification"]["revision"] == gitlab_fixture()["expected_revision"]
    observations, created = reconcile_observation((), snapshot)
    repeated, repeated_created = reconcile_observation(observations, copy.deepcopy(snapshot))
    assert created and not repeated_created and repeated == observations


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda data: data["pipeline"].update(sha="b" * 40), "gitlab.pipeline.stale"),
        (lambda data: data["pipeline"].update(status="failed"), "gitlab.pipeline.unsuccessful"),
        (lambda data: data["pipeline"].update(ref="other"), "gitlab.pipeline.branch"),
        (lambda data: data["merge_request"].update(head_pipeline={"id": 2}), "gitlab.pipeline.unbound"),
        (lambda data: data["merge_request"].update(approved=False), "gitlab.review.unapproved"),
        (lambda data: data["merge_request"].update(draft=True), "gitlab.review.draft"),
        (lambda data: data["merge_request"].update(state="closed"), "gitlab.review.closed"),
    ],
)
def test_incomplete_gitlab_delivery_fails_closed(mutation, code):
    data = gitlab_fixture()
    mutation(data)
    snapshot = normalize_gitlab_delivery(**data)
    assert not snapshot["allowed"]
    assert code in {item["code"] for item in snapshot["blockers"]}


def test_external_failure_is_distinct_from_permission_denial():
    data = jira_fixture()
    del data["item"]["fields"]["status"]
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_work_item("jira", **data)
    assert error.value.code == "integration.fact.missing"
    assert authorize_operation("jira", "work-item-transition")["blockers"][0]["code"] == "jira.mode.denied"


def test_external_references_are_bounded_to_expected_origin_and_identity():
    data = jira_fixture()
    data["scope"] = "http://modern-ash.atlassian.net"
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_work_item("jira", **data)
    assert error.value.code == "integration.fact.url"

    gitlab = gitlab_fixture()
    gitlab["issue"]["web_url"] = "https://gitlab.example.com/other/project/-/issues/30"
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_gitlab_delivery(**gitlab)
    assert error.value.code == "integration.fact.path"

    standalone = gitlab_fixture()
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_work_item(
            "gitlab",
            scope=f"{standalone['origin']}/{standalone['project']}",
            observed_at=standalone["observed_at"],
            item={**standalone["issue"], "web_url": "https://evil.example/unrelated/-/issues/30"},
        )
    assert error.value.code == "integration.fact.origin"

    prefixed = gitlab_fixture()
    prefixed["issue"]["web_url"] = "https://gitlab.example.com/prefix/modern-ash/agora-ai-sdlc/-/issues/30"
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_work_item(
            "gitlab",
            scope=f"{prefixed['origin']}/{prefixed['project']}",
            observed_at=prefixed["observed_at"],
            item=prefixed["issue"],
        )
    assert error.value.code == "integration.fact.path"


@pytest.mark.parametrize("key", ["AGORA-30#token=secret", "AGORA-30?x=1", "../admin"])
def test_jira_key_cannot_escape_bounded_evidence_url(key):
    data = jira_fixture()
    data["item"]["key"] = key
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_work_item("jira", **data)
    assert error.value.code == "jira.key.invalid"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("issue", "../merge_requests/65", "gitlab.id.invalid"),
        ("merge_request", "../issues/30", "gitlab.id.invalid"),
        ("pipeline", "../issues/30", "gitlab.id.invalid"),
        ("project", "modern-ash/../other", "gitlab.project.invalid"),
        ("project", "modern-ash/%2e%2e/other", "gitlab.project.invalid"),
    ],
)
def test_gitlab_path_components_cannot_escape_project_scope(field, value, code):
    data = gitlab_fixture()
    if field == "issue":
        data["issue"]["iid"] = value
    elif field == "merge_request":
        data["merge_request"]["iid"] = value
    elif field == "pipeline":
        data["pipeline"]["id"] = value
    else:
        data["project"] = value
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_gitlab_delivery(**data)
    assert error.value.code == code


def test_gitlab_scope_rejects_empty_path_segments():
    data = gitlab_fixture()
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_work_item(
            "gitlab",
            scope="https://gitlab.example.com//modern-ash/agora-ai-sdlc",
            observed_at=data["observed_at"],
            item={
                **data["issue"],
                "web_url": "https://gitlab.example.com//modern-ash/agora-ai-sdlc/-/issues/30",
            },
        )
    assert error.value.code == "gitlab.project.invalid"


def test_reconciliation_rejects_mutation_at_same_source_revision():
    data = jira_fixture()
    original = normalize_work_item("jira", **data)
    changed_data = jira_fixture()
    changed_data["item"]["fields"]["status"]["name"] = "Done"
    changed = normalize_work_item("jira", **changed_data)
    with pytest.raises(FollowOnDeliveryError) as error:
        reconcile_observation((original,), changed)
    assert error.value.code == "integration.reconciliation.conflict"

    delivery = normalize_gitlab_delivery(**gitlab_fixture())
    changed_delivery_data = gitlab_fixture()
    changed_delivery_data["merge_request"]["approved"] = False
    changed_delivery = normalize_gitlab_delivery(**changed_delivery_data)
    with pytest.raises(FollowOnDeliveryError) as error:
        reconcile_observation((delivery,), changed_delivery)
    assert error.value.code == "integration.reconciliation.conflict"


def test_unknown_provider_mode_and_state_are_rejected():
    with pytest.raises(FollowOnDeliveryError, match="unknown provider"):
        load_profile("bitbucket")
    with pytest.raises(FollowOnDeliveryError, match="unknown permission mode"):
        authorize_operation("jira", "work-item-view", mode="owner")
    data = jira_fixture()
    data["item"]["fields"]["status"]["name"] = "Awaiting Cosmic Alignment"
    with pytest.raises(FollowOnDeliveryError) as error:
        normalize_work_item("jira", **data)
    assert error.value.code == "jira.state.unsupported"
