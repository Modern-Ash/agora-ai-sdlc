import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from agora.model import UsageSummary

from agora_ai_sdlc.runtime_selection import (
    Budget,
    Candidate,
    Route,
    RuntimeRef,
    budget_from_core,
    select_runtime,
)

FIXTURES = Path(__file__).parent / "fixtures" / "runtime-selection"
ALLOW = {"allowed": True, "blockers": []}


def runtime(id_, provider, model=None):
    return RuntimeRef(id_, "generic", provider, model or f"{id_}-model")


def candidate(id_, provider, projected=None, data=None, review=None):
    return Candidate(
        runtime(id_, provider),
        projected or {},
        data or ALLOW,
        review or ALLOW,
    )


def route(*candidates, signals=("quota", "runtime-unavailable", "budget-exhausted"), activity="implementation"):
    return Route(activity, tuple(candidates), signals)


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.parametrize("activity", ["planning", "implementation", "review", "security-review", "operations"])
def test_explicit_activity_preference_selects_first_candidate(activity):
    result = select_runtime(
        route(candidate("primary", "provider-a"), candidate("secondary", "provider-b"), activity=activity)
    )
    assert result["allowed"] and result["selected"]["id"] == "primary"
    assert result["selection_reason"] == f"configured preference for {activity}"
    assert result["fallback"] == {"used": False, "reason": None}


def test_core_quota_signal_selects_next_authorized_fallback():
    result = select_runtime(
        route(candidate("primary", "provider-a"), candidate("secondary", "provider-b")),
        signal="quota",
        current_runtime="primary",
    )
    assert result["allowed"] and result["selected"]["id"] == "secondary"
    assert result["fallback"] == {"used": True, "reason": "quota"}
    assert result["selection_reason"] == "authorized fallback after quota"


def test_ordinary_failure_never_changes_provider():
    result = select_runtime(
        route(candidate("primary", "provider-a"), candidate("secondary", "provider-b")),
        signal="ordinary-failure",
        current_runtime="primary",
    )
    assert not result["allowed"] and result["selected"] is None
    assert result["blockers"][0]["code"] == "fallback.ordinary_failure"
    assert result["considered"] == ()


def test_budget_exhaustion_selects_only_authorized_affordable_fallback():
    data = fixture("budget-limit.json")
    budget = Budget(data["scope"], data["limits"], data["consumed"])
    result = select_runtime(
        route(
            candidate("primary", "provider-a", data["primary_projected"]),
            candidate("secondary", "provider-b", data["fallback_projected"]),
        ),
        budgets=(budget,),
    )
    assert result["allowed"] and result["selected"]["id"] == "secondary"
    assert result["fallback"] == {"used": True, "reason": "budget-exhausted"}
    assert result["consumed_budget"] == {"work:build": {"cost-micros": 900}}


def test_budget_exhaustion_blocks_when_fallback_signal_is_not_authorized():
    data = fixture("budget-limit.json")
    result = select_runtime(
        route(
            candidate("primary", "provider-a", data["primary_projected"]),
            candidate("secondary", "provider-b", data["fallback_projected"]),
            signals=("quota",),
        ),
        budgets=(Budget(data["scope"], data["limits"], data["consumed"]),),
    )
    assert not result["allowed"] and result["selected"] is None
    assert result["fallback"]["reason"] == "budget-exhausted"
    assert result["blockers"][0]["code"] == "fallback.unauthorized_signal"
    assert result["considered"] == ({"runtime": "primary", "blockers": ("budget.exhausted",)},)


def test_unknown_cost_is_not_zero():
    data = fixture("unknown-cost.json")
    result = select_runtime(
        route(candidate("primary", "provider-a", data["projected"])),
        budgets=(Budget(data["scope"], data["limits"], data["consumed"]),),
    )
    assert not result["allowed"] and result["selected"] is None
    assert result["fallback"]["reason"] == "budget-unavailable"
    assert result["considered"] == ({"runtime": "primary", "blockers": ("budget.unavailable",)},)


def test_unknown_cost_uses_only_an_explicitly_authorized_known_cost_fallback():
    data = fixture("unknown-cost.json")
    result = select_runtime(
        route(
            candidate("primary", "provider-a", data["projected"]),
            candidate("secondary", "provider-b", {"cost-micros": 100}),
            signals=("budget-unavailable",),
        ),
        budgets=(Budget(data["scope"], data["limits"], data["consumed"]),),
    )
    assert result["allowed"] and result["selected"]["id"] == "secondary"
    assert result["fallback"] == {"used": True, "reason": "budget-unavailable"}


@pytest.mark.parametrize("policy", ["data", "review"])
def test_fallback_candidate_must_pass_data_and_review_policy(policy):
    blocked = {"allowed": False, "blockers": [{"code": f"{policy}.blocked"}]}
    kwargs = {policy: blocked}
    result = select_runtime(
        route(
            candidate("primary", "provider-a"),
            candidate("secondary", "provider-b", **kwargs),
        ),
        signal="quota",
    )
    assert not result["allowed"] and result["selected"] is None
    assert result["considered"][0]["blockers"] == (f"runtime.{policy}_policy",)


def test_core_usage_summary_maps_to_durable_budget_facts():
    summary = UsageSummary(
        swarm_id="swarm-1",
        work_id="work-1",
        budget_limits={"tokens": 1000, "cost-micros": 500},
        consumed={"tokens": 250},
        remaining={"tokens": 750, "cost-micros": 500},
        records=1,
    )
    budget = budget_from_core(summary, scope="work:swarm-1/work-1")
    assert budget.limits == {"tokens": 1000, "cost-micros": 500}
    assert budget.consumed == {"tokens": 250, "cost-micros": None}


def test_core_usage_summary_with_no_records_starts_at_zero():
    summary = UsageSummary(
        swarm_id="swarm-1",
        work_id="work-1",
        budget_limits={"tokens": 1000},
        consumed={},
        remaining={"tokens": 1000},
        records=0,
    )
    assert budget_from_core(summary, scope="work:swarm-1/work-1").consumed == {"tokens": 0}


def test_selection_is_deterministic_and_rejects_unstructured_failure_signals():
    configured = route(candidate("primary", "provider-a"), candidate("secondary", "provider-b"))
    assert select_runtime(configured, signal="quota") == select_runtime(configured, signal="quota")
    with pytest.raises(ValueError, match="unsupported Core failure signal"):
        select_runtime(configured, signal="HTTP 429 in provider log")


@dataclass
class UsageFacts:
    """Structural stand-in for Core's UsageSummary so the test runs on any supported Core."""

    budget_limits: dict[str, int] | None
    consumed: dict[str, int]
    records: int
    consumed_measurement: dict[str, str] | None = None


def core_facts(**changes):
    values = {
        "budget_limits": {"tokens": 1000, "cost-micros": 500},
        "consumed": {"tokens": 250, "cost-micros": 100},
        "records": 2,
        "consumed_measurement": {"tokens": "provider-reported", "cost-micros": "measured"},
    }
    values.update(changes)
    return UsageFacts(**values)


def test_core_measurement_basis_is_carried_per_dimension_into_the_decision():
    budget = budget_from_core(core_facts(), scope="work:swarm-1/work-1")
    assert budget.measurement == {"tokens": "provider-reported", "cost-micros": "measured"}
    result = select_runtime(route(candidate("primary", "provider-a", {"tokens": 10})), budgets=(budget,))
    assert result["consumed_budget"] == {"work:swarm-1/work-1": {"cost-micros": 100, "tokens": 250}}
    assert result["consumed_measurement"] == {
        "work:swarm-1/work-1": {"cost-micros": "measured", "tokens": "provider-reported"}
    }


def test_missing_measurement_is_unknown_never_measured():
    older_core = budget_from_core(core_facts(consumed_measurement=None), scope="work:a/b")
    partial = budget_from_core(core_facts(consumed_measurement={"tokens": "measured"}), scope="work:a/b")
    no_records = budget_from_core(core_facts(records=0, consumed={}), scope="work:a/b")
    assert set(older_core.measurement.values()) == {"unknown"}
    assert partial.measurement == {"tokens": "measured", "cost-micros": "unknown"}
    assert set(no_records.measurement.values()) == {"unknown"}
    assert no_records.consumed == {"tokens": 0, "cost-micros": 0}


def test_every_decision_shape_reports_the_measurement_basis():
    budget = budget_from_core(core_facts(), scope="work:a/b")
    expected = {"work:a/b": {"cost-micros": "measured", "tokens": "provider-reported"}}
    shapes = (
        select_runtime(route(candidate("primary", "provider-a")), budgets=(budget,)),
        select_runtime(route(candidate("primary", "provider-a")), budgets=(budget,), signal="ordinary-failure"),
        select_runtime(route(candidate("primary", "provider-a"), signals=()), budgets=(budget,), signal="quota"),
        select_runtime(route(candidate("primary", "provider-a", {"tokens": 5000})), budgets=(budget,)),
    )
    for result in shapes:
        assert result["consumed_measurement"] == expected


def test_unsupported_measurement_basis_is_rejected():
    budget = Budget("work:a/b", {"tokens": 10}, {"tokens": 1}, {"tokens": "estimated"})
    with pytest.raises(ValueError, match="measured, provider-reported or unknown"):
        select_runtime(route(candidate("primary", "provider-a")), budgets=(budget,))


def test_budget_decisions_do_not_depend_on_the_measurement_basis():
    for basis in ("measured", "provider-reported", "unknown"):
        budget = Budget("work:a/b", {"tokens": 100}, {"tokens": 90}, {"tokens": basis})
        result = select_runtime(route(candidate("primary", "provider-a", {"tokens": 20})), budgets=(budget,))
        assert not result["allowed"] and result["fallback"]["reason"] == "budget-exhausted"
