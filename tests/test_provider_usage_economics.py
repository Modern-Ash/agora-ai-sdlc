from agora_ai_sdlc.execution_economics import EconomicsEvent, record_event, summarize_economics


def test_summary_aggregates_only_provider_reported_usage(tmp_path):
    for input_tokens, output_tokens in ((100, 20), (50, 10)):
        record_event(
            tmp_path,
            EconomicsEvent(
                "success",
                "issue-1",
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
            ),
        )

    record_event(
        tmp_path,
        EconomicsEvent(
            "success",
            "issue-1",
            "local",
            "other",
            "model",
            purpose="executor",
            measurement={
                "provider_usage": {
                    "basis": "estimated_tokens",
                    "input_tokens": 999,
                    "output_tokens": 999,
                }
            },
        ),
    )

    summary = summarize_economics(tmp_path, "issue-1")

    assert summary["provider_usage"] == {
        "basis": "provider_reported_tokens",
        "input_tokens": 150,
        "output_tokens": 30,
        "total_tokens": 180,
        "events": 2,
    }


def test_attempt_event_does_not_double_count_provider_usage(tmp_path):
    record_event(
        tmp_path,
        EconomicsEvent(
            "attempt",
            "issue-2",
            "paid-efficient",
            "claude",
            "sonnet",
            measurement={
                "provider_usage": {
                    "basis": "provider_reported_tokens",
                    "input_tokens": 100,
                    "output_tokens": 20,
                }
            },
        ),
    )

    assert summarize_economics(tmp_path, "issue-2")["provider_usage"] is None
