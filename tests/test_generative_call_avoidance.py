from agora_ai_sdlc.execution_economics import (
    EconomicsEvent,
    record_decision_event,
    record_event,
    render_economics,
    summarize_economics,
)


def test_economics_counts_only_observed_call_avoidance(tmp_path):
    record_decision_event(
        tmp_path,
        work="issue-1",
        route="system0",
        reason="planner-none",
        generative_call=False,
        tier="system0",
        measurement={
            "call_avoided": True,
            "avoidance_reason": "planner-none",
        },
    )
    record_decision_event(
        tmp_path,
        work="issue-1",
        route="laya",
        reason="classification-only",
        generative_call=False,
        tier="system1",
    )
    record_decision_event(
        tmp_path,
        work="issue-1",
        route="generative",
        reason="planner-generative",
        generative_call=True,
        tier="paid-efficient",
    )

    summary = summarize_economics(tmp_path, "issue-1")

    assert summary["generative_calls_observed"] == 1
    assert summary["generative_calls_avoided"] == 1
    assert summary["avoidance_reasons"] == {"planner-none": 1}
    assert "Observed generative calls avoided: 1" in render_economics(tmp_path, "issue-1")


def test_non_decision_events_do_not_claim_avoided_calls(tmp_path):
    record_event(
        tmp_path,
        EconomicsEvent(
            "success",
            "issue-2",
            "local",
            "opencode",
            "local-model",
            purpose="executor",
            measurement={"call_avoided": True},
        ),
    )

    summary = summarize_economics(tmp_path, "issue-2")

    assert summary["generative_calls_avoided"] == 0
    assert summary["avoidance_reasons"] == {}
