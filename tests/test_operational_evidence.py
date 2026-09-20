import copy
import json
from pathlib import Path

import pytest
from agora.filesystem import packs_root
from agora.tools import load_tool_contract

from agora_ai_sdlc.operational_evidence import (
    OperationalEvidenceError,
    control_band_inputs,
    core_evidence_input,
    evaluate_readiness,
    load_profile,
    normalize_metric,
    normalize_release_observation,
)
from agora_ai_sdlc.scenario import Lifecycle

FIXTURES = Path(__file__).parents[1] / "samples" / "operational-evidence"
NOW = "2026-09-20T15:02:00Z"
RELEASE = "product-2026.09.20"
REVISION = "a" * 40
ENVIRONMENT = "production"


def metric_payloads():
    return json.loads((FIXTURES / "metrics.json").read_text(encoding="utf-8"))


def release_payloads():
    return json.loads((FIXTURES / "releases.json").read_text(encoding="utf-8"))


def metric(item, environment=ENVIRONMENT, now=NOW):
    return normalize_metric(item["provider"], item["payload"], expected_environment=environment, observed_at=now)


def release(item, **overrides):
    arguments = {
        "expected_release": RELEASE,
        "expected_revision": REVISION,
        "expected_environment": ENVIRONMENT,
        "observed_at": NOW,
        **overrides,
    }
    return normalize_release_observation(item, **arguments)


def readiness(metrics=None, releases=None):
    return evaluate_readiness(
        metrics if metrics is not None else [metric(item) for item in metric_payloads()],
        releases if releases is not None else [release(item) for item in release_payloads()],
        expected_release=RELEASE,
        expected_revision=REVISION,
        expected_environment=ENVIRONMENT,
    )


def test_profile_uses_installed_neutral_observability_contract_without_provider_dependencies():
    profile = load_profile()
    contract = load_tool_contract(packs_root() / "tools" / profile["core_tool"])
    assert contract.id == "observability"
    for expected in profile["operations"].values():
        operation = contract.operations[expected["operation"]]
        assert (operation.capability, operation.risk) == (expected["capability"], expected["risk"])
    assert profile["provider_examples"] == [
        "cloudwatch",
        "azure-monitor",
        "gcp-monitoring",
        "prometheus",
        "opentelemetry",
    ]


def test_five_provider_fixtures_normalize_to_equivalent_neutral_metrics():
    facts = [metric(item) for item in metric_payloads()]
    assert {fact["provider"] for fact in facts} == set(load_profile()["provider_examples"])
    assert {
        (fact["name"], fact["value"], fact["unit"], fact["window"], fact["environment"], fact["timestamp"])
        for fact in facts
    } == {("http.error_rate", 0.75, "percent", "5m", "production", "2026-09-20T15:00:00Z")}
    assert all(fact["allowed"] for fact in facts)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda item: item["payload"].update(Environment="staging"), "observability.environment.mismatch"),
        (lambda item: item["payload"].update(Timestamp="2026-09-20T14:00:00Z"), "observability.timestamp.stale"),
        (lambda item: item["payload"].update(Timestamp="2026-09-20T16:00:00Z"), "observability.timestamp.future"),
    ],
)
def test_wrong_environment_stale_and_future_metrics_cannot_satisfy_readiness(mutation, code):
    item = copy.deepcopy(metric_payloads()[0])
    mutation(item)
    fact = metric(item)
    assert not fact["allowed"] and code in {blocker["code"] for blocker in fact["blockers"]}
    result = readiness(metrics=[fact])
    assert not result["allowed"] and result["blockers"][0]["code"] == "observability.readiness.metric"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("unit", None, "observability.fact.unit"),
        ("timeGrain", None, "observability.fact.window"),
    ],
)
def test_missing_unit_or_window_is_a_validation_error(field, value, code):
    item = copy.deepcopy(metric_payloads()[1])
    item["payload"][field] = value
    with pytest.raises(OperationalEvidenceError) as error:
        metric(item)
    assert error.value.code == code


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("release", "product-old", "observability.release.mismatch"),
        ("revision", "b" * 40, "observability.revision.stale"),
        ("environment", "staging", "observability.environment.mismatch"),
        ("status", "failure", "observability.release.unsuccessful"),
        ("timestamp", "2026-09-20T14:00:00Z", "observability.timestamp.stale"),
    ],
)
def test_noncurrent_release_observations_cannot_satisfy_readiness(field, value, code):
    payload = copy.deepcopy(release_payloads()[0])
    payload[field] = value
    fact = release(payload)
    assert not fact["allowed"] and code in {blocker["code"] for blocker in fact["blockers"]}
    result = readiness(releases=[fact])
    assert not result["allowed"]


def test_complete_current_release_maps_to_core_deployment_evidence():
    result = readiness()
    assert result["allowed"] and len(result["evidence_refs"]) == 3
    core = core_evidence_input(result, swarm_id="delivery", work_id="feature", actor_id="operator")
    assert core.type == "deployment" and core.result == "success"
    assert core.tested_commit == REVISION and core.environment == ENVIRONMENT and core.dedupe_key


def test_missing_smoke_or_metric_maps_to_failed_core_evidence():
    result = readiness(metrics=[], releases=[release(release_payloads()[0])])
    assert not result["allowed"]
    assert {blocker["code"] for blocker in result["blockers"]} == {
        "observability.readiness.metric",
        "observability.readiness.release",
    }
    assert core_evidence_input(result, swarm_id="delivery", work_id="feature", actor_id="operator").result == "failure"


def test_readiness_dedupe_identity_includes_release_context_even_when_blocked():
    first = readiness(metrics=[], releases=[])
    second = evaluate_readiness(
        [],
        [],
        expected_release="product-2026.09.21",
        expected_revision="b" * 40,
        expected_environment=ENVIRONMENT,
    )
    assert first["dedupe_key"] != second["dedupe_key"]


@pytest.mark.parametrize(
    "source",
    [
        "http://metrics.example/result",
        "https://user:secret@metrics.example/result",
        "https://metrics.example/result?token=secret",
        "https://metrics.example/result#secret",
        "file:///tmp/result",
    ],
)
def test_metric_sources_are_bounded_and_secret_safe(source):
    item = copy.deepcopy(metric_payloads()[1])
    item["payload"]["portalUrl"] = source
    with pytest.raises(OperationalEvidenceError) as error:
        metric(item)
    assert error.value.code == "observability.fact.source"


def test_severe_control_band_result_creates_governed_intent_without_operational_write(tmp_path):
    item = copy.deepcopy(metric_payloads()[0])
    item["payload"]["Average"] = 2.0
    fact = metric(item)
    band, evaluation = control_band_inputs(fact, "severe-signal")
    lifecycle = Lifecycle(tmp_path / "project", tmp_path / "home")
    lifecycle.ws.add_control_band(band)
    finding = lifecycle.ws.evaluate_control_band(evaluation)
    assert finding.level == "propose" and finding.intent_id
    intent = next(intent for intent in lifecycle.ws.list_intents() if intent.id == finding.intent_id)
    assert intent.status == "draft" and intent.source.endswith("/findings/severe-signal")
    assert not list((tmp_path / "project" / ".agora" / "tool-runs").glob("*/RUN.md"))


def test_blocked_metric_cannot_enter_control_band():
    fact = metric(metric_payloads()[0], environment="staging")
    with pytest.raises(OperationalEvidenceError) as error:
        control_band_inputs(fact, "blocked")
    assert error.value.code == "observability.control-band.blocked"
