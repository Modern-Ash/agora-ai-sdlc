from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.risk_issue_management import RiskIssueError, parse_record, portfolio

ROOT = Path(__file__).parent.parent
SAMPLES = ROOT / "samples" / "risk-issue-management"


def load(name: str):
    return parse_record((SAMPLES / name).read_text(encoding="utf-8"))


def mutate(name: str, fn) -> str:
    data = yaml.safe_load((SAMPLES / name).read_text(encoding="utf-8"))
    fn(data)
    return yaml.safe_dump(data, sort_keys=False)


def code(fn) -> str:
    with pytest.raises(RiskIssueError) as exc:
        fn()
    return exc.value.code


def test_risk_and_issue_records_parse_and_portfolio_is_deterministic():
    risk = load("risk.yaml")
    issue = load("issue.yaml")
    summary = portfolio((issue, risk))

    assert risk.type == "risk"
    assert issue.type == "issue"
    assert summary["total"] == 2
    assert summary["open"] == 1
    assert summary["blocking"] == 0
    assert summary["records"][0]["id"] == "ISS-001"
    assert summary["records"][1]["id"] == "RSK-001"


def test_open_high_or_critical_record_is_blocking():
    issue = parse_record(
        mutate(
            "issue.yaml",
            lambda data: data.update({"status": "open", "evidence": [], "severity": "critical"}),
        )
    )
    summary = portfolio((issue,))
    assert summary["blocking"] == 1
    assert summary["blocking_ids"] == ["ISS-001"]


def test_risk_requires_probability_and_mitigation():
    assert code(lambda: parse_record(mutate("risk.yaml", lambda data: data.update({"probability": None})))) == (
        "risk-issue.probability"
    )
    assert code(lambda: parse_record(mutate("risk.yaml", lambda data: data.update({"mitigation": None})))) == (
        "risk-issue.mitigation"
    )


def test_issue_requires_next_action_and_no_probability():
    assert code(lambda: parse_record(mutate("issue.yaml", lambda data: data.update({"next_action": None})))) == (
        "risk-issue.next_action"
    )
    assert code(lambda: parse_record(mutate("issue.yaml", lambda data: data.update({"probability": "high"})))) == (
        "risk-issue.probability"
    )


def test_closed_or_resolved_records_require_evidence():
    assert code(lambda: parse_record(mutate("issue.yaml", lambda data: data.update({"evidence": []})))) == (
        "risk-issue.closure_evidence"
    )


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("https://tracker.example/issues/1", "risk-issue.endpoint"),
        ("tracker:issue/1?token=secret-value", "risk-issue.secret"),
        ("not a reference", "risk-issue.evidence"),
    ],
)
def test_evidence_references_are_opaque_and_secret_safe(reference, expected):
    assert (
        code(lambda: parse_record(mutate("risk.yaml", lambda data: data.update({"evidence": [reference]})))) == expected
    )


def test_duplicate_record_ids_fail_closed():
    risk = load("risk.yaml")
    assert code(lambda: portfolio((risk, risk))) == "risk-issue.duplicate_id"
