from types import SimpleNamespace

from agora_ai_sdlc.execution_economics import (
    record_advisory_decision_event,
    render_economics,
    summarize_economics,
)


def evaluation(*, accepted=("reasoning_tier",), escalated=("change_risk",), latency=4.5, provider_calls=1):
    answers = {
        "reasoning_tier": SimpleNamespace(confidence=0.97),
        "change_risk": SimpleNamespace(confidence=0.61),
    }
    return SimpleNamespace(
        accepted=accepted,
        escalated=escalated,
        result=SimpleNamespace(
            provider="laya",
            model="typed-decisions",
            latency_ms=latency,
            answers=answers,
            metadata={"provider_calls": provider_calls},
        ),
    )


def test_advisory_summary_exposes_observed_laya_quality_without_claiming_savings(tmp_path):
    record_advisory_decision_event(
        tmp_path,
        work="issue-90",
        evaluation=evaluation(),
        confidence_threshold=0.90,
    )
    record_advisory_decision_event(
        tmp_path,
        work="issue-90",
        evaluation=evaluation(
            accepted=("reasoning_tier", "change_risk"),
            escalated=(),
            latency=2.5,
            provider_calls=0,
        ),
        confidence_threshold=0.90,
        cache_hit=True,
    )

    summary = summarize_economics(tmp_path, "issue-90")

    assert summary["advisory"] == {
        "decisions": 2,
        "accepted": 3,
        "escalated": 1,
        "acceptance_rate": 0.75,
        "low_confidence_rate": 0.25,
        "latency_ms": 7.0,
        "provider_calls": 1,
        "cache_hits": 1,
        "mean_confidence": {"change_risk": 0.61, "reasoning_tier": 0.97},
    }
    assert summary["generative_calls_avoided"] == 0


def test_render_reports_laya_metrics_and_preserves_counterfactual_warning(tmp_path):
    record_advisory_decision_event(
        tmp_path,
        work="issue-90",
        evaluation=evaluation(escalated=()),
        confidence_threshold=0.90,
    )

    rendered = render_economics(tmp_path, "issue-90")

    assert "Laya/System-1 advisory: 1 evaluations" in rendered
    assert "acceptance_rate=100.00%" in rendered
    assert "No counterfactual token or monetary savings are claimed" in rendered
