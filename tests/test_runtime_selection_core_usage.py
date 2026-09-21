"""Real Agora Core usage measurement basis feeding runtime-selection budgets (Core >= 0.9.1)."""

import pytest
from agora.model import AddUsageInput, UsageSummary

from agora_ai_sdlc.runtime_selection import Candidate, Route, RuntimeRef, budget_from_core, select_runtime
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle

pytestmark = pytest.mark.skipif(
    "consumed_measurement" not in UsageSummary.__dataclass_fields__,
    reason="usage measurement basis needs Agora Core >=0.9.1",
)


def record(life, usage_id, amounts, measurement=None):
    life.ws.add_usage(
        AddUsageInput(
            id=usage_id,
            swarm_id=SWARM,
            work_id=WORK,
            actor_id="ops",
            amounts=amounts,
            evidence_refs=["repo://evidence/metering.md"],
            measurement=measurement,
        )
    )


def decision(life):
    summary = life.ws.summarize_usage(SWARM, WORK)
    budget = budget_from_core(summary, scope=f"work:{SWARM}/{WORK}")
    candidate = Candidate(
        RuntimeRef("primary", "generic", "provider-a", "model"),
        dict.fromkeys(budget.limits, 1),
        ALLOW,
        ALLOW,
    )
    return budget, select_runtime(Route("implementation", (candidate,), ()), budgets=(budget,))


ALLOW = {"allowed": True, "blockers": []}


def limited(life, limits):
    from pathlib import Path

    from agora.markdown import read_markdown, render_markdown

    path = Path(life.ws.show_work(SWARM, WORK).path) / "WORK.md"
    document = read_markdown(path)
    document.attributes["budget-limits"] = limits
    path.write_text(render_markdown(document), encoding="utf-8")


def test_measurement_from_real_core_reaches_the_selection_decision(tmp_path):
    life = Lifecycle(tmp_path / "project", tmp_path / "home")
    limited(life, {"tokens": 1000, "cost-cents": 500})
    record(life, "m1", {"tokens": 10, "cost-cents": 5}, "measured")
    record(life, "r1", {"tokens": 10}, "provider-reported")
    budget, result = decision(life)
    assert budget.measurement == {"tokens": "provider-reported", "cost-cents": "measured"}
    scope = f"work:{SWARM}/{WORK}"
    assert result["consumed_measurement"] == {scope: {"cost-cents": "measured", "tokens": "provider-reported"}}
    assert result["allowed"]


def test_legacy_usage_without_a_basis_is_reported_unknown_by_the_flavor(tmp_path):
    life = Lifecycle(tmp_path / "project", tmp_path / "home")
    limited(life, {"tokens": 1000})
    record(life, "m1", {"tokens": 10}, "measured")
    record(life, "legacy", {"tokens": 10})
    budget, result = decision(life)
    assert budget.measurement == {"tokens": "unknown"}
    assert result["consumed_measurement"][f"work:{SWARM}/{WORK}"] == {"tokens": "unknown"}
