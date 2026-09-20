import copy
import json
from pathlib import Path

import pytest
from agora.filesystem import packs_root
from agora.tools import load_tool_contract

from agora_ai_sdlc.security_findings import (
    SecurityFindingError,
    decide_finding,
    evaluate_findings,
    load_profile,
    normalize_finding,
    security_evidence_input,
    to_core_decision_input,
    to_core_finding_input,
)

FIXTURE = Path(__file__).parents[1] / "samples" / "security-findings" / "fixtures.json"
SCAN_REF = "https://security.example.com/reports/change-42"
COMMIT = "a" * 40


def entries():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def payload(**updates):
    value = entries()[0]["finding"]
    value.update(updates)
    return value


def assessment(depth, findings):
    return evaluate_findings(depth, findings, scan_refs=[SCAN_REF])


def decision(kind="resolved", **updates):
    value = {
        "kind": kind,
        "actor": "security",
        "actor_kind": "human",
        "role": "security-reviewer",
        "reason": "The finding was independently verified and remediated.",
        "evidence_ref": "https://governance.example.com/security/decisions/change-42",
    }
    value.update(updates)
    return value


def test_profile_matches_core_security_contract_and_preserves_rich_decisions():
    profile = load_profile()
    neutral = load_tool_contract(packs_root() / "tools" / profile["core_tool"])
    assert neutral.id == "security-scanning"
    assert set(neutral.operations) == {"list-code-alerts", "list-dependency-alerts", "list-secret-alerts"}
    assert profile["decisions"]["resolved"]["core_status"] == "resolved"
    assert profile["decisions"]["accepted-risk"]["core_status"] == "waived"
    assert profile["decisions"]["false-positive"]["core_status"] == "waived"


@pytest.mark.parametrize("depth", ["minimal", "standard", "comprehensive", "regulated"])
@pytest.mark.parametrize("severity", ["low", "medium", "high", "critical"])
def test_severity_threshold_matrix(depth, severity):
    profile = load_profile()
    finding = normalize_finding(payload(severity=severity))
    result = assessment(depth, [finding])
    expected = profile["severity_rank"][severity] >= profile["severity_rank"][profile["thresholds"][depth]]
    assert result["allowed"] is not expected
    assert bool(result["blockers"]) is expected


@pytest.mark.parametrize("depth", ["minimal", "standard", "comprehensive", "regulated"])
def test_unknown_severity_fails_closed_for_every_depth(depth):
    result = assessment(depth, [normalize_finding(payload(severity="unknown"))])
    assert not result["allowed"]
    assert result["blockers"][0]["code"] == "security.severity.unknown"


def test_scanner_name_does_not_change_semantic_behavior():
    first = normalize_finding(payload(scanner="scanner-a"))
    second = normalize_finding(payload(scanner="completely-different-scanner"))
    first_result = assessment("standard", [first])
    second_result = assessment("standard", [second])
    assert first_result["allowed"] == second_result["allowed"]
    assert [item["code"] for item in first_result["blockers"]] == [item["code"] for item in second_result["blockers"]]


def test_assessment_is_order_independent_and_rejects_duplicate_ids():
    first = normalize_finding(payload(id="first", severity="low"))
    second = normalize_finding(payload(id="second", severity="critical"))
    assert assessment("standard", [first, second]) == assessment("standard", [second, first])
    with pytest.raises(SecurityFindingError) as error:
        assessment("standard", [first, copy.deepcopy(first)])
    assert error.value.code == "security.findings.duplicate"


def test_decisions_preserve_original_finding_and_map_to_core():
    original = normalize_finding(payload())
    original_fields = {key: original[key] for key in original if key not in {"status", "decision", "fingerprint"}}
    resolved = decide_finding(original, decision())
    assert original["status"] == "open" and original["decision"] is None
    assert {key: resolved[key] for key in original_fields} == original_fields
    assert resolved["original_fingerprint"] == original["original_fingerprint"]
    assert resolved["status"] == "resolved"
    core_finding = to_core_finding_input(original, swarm_id="delivery", work_id="feature")
    core_decision = to_core_decision_input(resolved)
    assert core_finding.pass_id == "security-sast" and core_finding.severity == "high"
    assert core_decision.decision == "resolved" and core_decision.actor == "security"


@pytest.mark.parametrize(
    ("kind", "role", "actor_kind", "code"),
    [
        ("accepted-risk", "security-reviewer", "human", "security.decision.role"),
        ("accepted-risk", "governance-owner", "ai-agent", "security.decision.actor_kind"),
        ("false-positive", "governance-owner", "human", "security.decision.role"),
        ("resolved", "governance-owner", "human", "security.decision.role"),
    ],
)
def test_decision_authority_fails_closed(kind, role, actor_kind, code):
    with pytest.raises(SecurityFindingError) as error:
        decide_finding(
            normalize_finding(payload()),
            decision(kind, role=role, actor_kind=actor_kind),
        )
    assert error.value.code == code


def test_human_governance_owner_can_accept_risk_without_deleting_finding():
    original = normalize_finding(payload(severity="critical"))
    waived = decide_finding(
        original,
        decision(
            "accepted-risk",
            actor="governance",
            role="governance-owner",
            actor_kind="human",
            reason="Compensating control approved until a fixed upstream release.",
        ),
    )
    assert assessment("regulated", [waived])["allowed"]
    assert waived["original_fingerprint"] == original["original_fingerprint"]
    assert to_core_decision_input(waived).decision == "waived"


@pytest.mark.parametrize("field", ["actor", "actor_kind", "role", "reason", "evidence_ref"])
def test_incomplete_decision_is_rejected(field):
    value = decision()
    value.pop(field)
    with pytest.raises(SecurityFindingError) as error:
        decide_finding(normalize_finding(payload()), value)
    assert error.value.code == "security.decision.fields"


@pytest.mark.parametrize(
    "reference",
    [
        "http://security.example.com/report/1",
        "https://user:password@security.example.com/report/1",
        "https://security.example.com/report/1?token=secret",
        "https://security.example.com/report/1#secret",
        "file:///tmp/raw.sarif",
    ],
)
def test_raw_reports_and_decision_evidence_are_safe_external_references(reference):
    with pytest.raises(SecurityFindingError) as error:
        normalize_finding(payload(report_ref=reference))
    assert error.value.code == "security.finding.reference"
    with pytest.raises(SecurityFindingError) as error:
        decide_finding(normalize_finding(payload()), decision(evidence_ref=reference))
    assert error.value.code == "security.finding.reference"


def test_raw_report_bodies_and_unknown_categories_are_rejected():
    value = payload()
    value["raw_report"] = {"results": []}
    with pytest.raises(SecurityFindingError) as error:
        normalize_finding(value)
    assert error.value.code == "security.finding.fields"
    with pytest.raises(SecurityFindingError) as error:
        normalize_finding(payload(category="dast"))
    assert error.value.code == "security.finding.category"


def test_original_finding_mutation_after_decision_is_detected():
    decided = decide_finding(normalize_finding(payload()), decision())
    changed = copy.deepcopy(decided)
    changed["severity"] = "low"
    with pytest.raises(SecurityFindingError) as error:
        assessment("standard", [changed])
    assert error.value.code == "security.finding.mutated"


def test_security_scan_evidence_is_success_only_after_blockers_are_decided():
    original = normalize_finding(payload(severity="critical"))
    blocked = assessment("standard", [original])
    failed = security_evidence_input(
        blocked,
        swarm_id="delivery",
        work_id="feature",
        actor_id="security",
        tested_commit=COMMIT,
        environment="ci",
    )
    assert failed.result == "failure"
    resolved = decide_finding(original, decision())
    allowed = assessment("standard", [resolved])
    successful = security_evidence_input(
        allowed,
        swarm_id="delivery",
        work_id="feature",
        actor_id="security",
        tested_commit=COMMIT,
        environment="ci",
    )
    assert successful.result == "success" and successful.type == "security-scan"
    assert successful.tested_commit == COMMIT and successful.dedupe_key


def test_unknown_depth_decision_and_invalid_commit_are_rejected():
    finding = normalize_finding(payload())
    with pytest.raises(SecurityFindingError, match="unknown depth"):
        assessment("custom", [finding])
    with pytest.raises(SecurityFindingError, match="unsupported decision"):
        decide_finding(finding, decision("ignored"))
    with pytest.raises(SecurityFindingError) as error:
        security_evidence_input(
            assessment("standard", [decide_finding(finding, decision())]),
            swarm_id="delivery",
            work_id="feature",
            actor_id="security",
            tested_commit="abc123",
            environment="ci",
        )
    assert error.value.code == "security.evidence.commit"
