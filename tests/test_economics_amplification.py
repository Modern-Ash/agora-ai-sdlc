from agora_ai_sdlc.amplification import TokenMeasurement, save_baseline
from agora_ai_sdlc.execution_economics import EconomicsEvent, record_event, render_economics, summarize_economics


def usage_event(input_tokens, output_tokens):
    return EconomicsEvent(
        "success",
        "issue-af",
        "paid-efficient",
        "claude",
        "sonnet",
        purpose="executor",
        measurement={
            "provider_usage": {
                "basis": "provider_reported_tokens",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        },
    )


def test_economics_aggregates_provider_usage_and_renders_measured_af(tmp_path):
    record_event(tmp_path, usage_event(400, 100))
    record_event(tmp_path, usage_event(200, 50))
    save_baseline(tmp_path, "issue-af", TokenMeasurement(800, 200))

    summary = summarize_economics(tmp_path, "issue-af")
    rendered = render_economics(tmp_path, "issue-af")

    assert summary["provider_usage"]["total_tokens"] == 750
    assert summary["provider_usage"]["events"] == 2
    assert "LLM Amplification Factor: 0.7500" in rendered


def test_economics_renders_unknown_af_without_direct_baseline(tmp_path):
    record_event(tmp_path, usage_event(100, 20))

    rendered = render_economics(tmp_path, "issue-af")

    assert "Provider tokens: 120" in rendered
    assert "LLM Amplification Factor: unknown (baseline-missing)" in rendered


def test_invalid_usage_is_not_aggregated(tmp_path):
    record_event(
        tmp_path,
        EconomicsEvent(
            "success",
            "issue-af",
            "paid-efficient",
            "claude",
            "sonnet",
            measurement={
                "provider_usage": {
                    "basis": "estimated_tokens",
                    "input_tokens": 999,
                    "output_tokens": 999,
                }
            },
        ),
    )

    assert summarize_economics(tmp_path, "issue-af")["provider_usage"] is None
