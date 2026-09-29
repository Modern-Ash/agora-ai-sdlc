import json

from agora_ai_sdlc.cli import main
from agora_ai_sdlc.execution_economics import EconomicsEvent, record_event


def record_usage(root):
    record_event(
        root,
        EconomicsEvent(
            "success",
            "issue-42",
            "paid-efficient",
            "claude",
            "sonnet",
            purpose="executor",
            measurement={
                "provider_usage": {
                    "basis": "provider_reported_tokens",
                    "input_tokens": 600,
                    "output_tokens": 150,
                }
            },
        ),
    )


def test_economics_cli_persists_baseline_and_shows_measured_af(tmp_path, capsys):
    record_usage(tmp_path)

    code = main(
        [
            "economics",
            "--root",
            str(tmp_path),
            "--work",
            "issue-42",
            "--baseline-input-tokens",
            "800",
            "--baseline-output-tokens",
            "200",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Provider tokens: 750" in output
    assert "LLM Amplification Factor: 0.7500" in output


def test_economics_json_includes_amplification(tmp_path, capsys):
    record_usage(tmp_path)
    main(
        [
            "economics",
            "--root",
            str(tmp_path),
            "--work",
            "issue-42",
            "--baseline-input-tokens",
            "800",
            "--baseline-output-tokens",
            "200",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["amplification"]["comparable"] is True
    assert payload["amplification"]["factor"] == 0.75


def test_economics_baseline_requires_both_values(tmp_path, capsys):
    code = main(
        [
            "economics",
            "--root",
            str(tmp_path),
            "--work",
            "issue-42",
            "--baseline-input-tokens",
            "800",
        ]
    )

    assert code == 2
    assert "both baseline token values" in capsys.readouterr().err
