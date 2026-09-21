from pathlib import Path

from agora_ai_sdlc.compatibility_profiles import load_profile
from agora_ai_sdlc.conformance.compatibility import evaluate
from agora_ai_sdlc.conformance.lg_enterprise import FACTS_SOURCE, RULES, derive_facts

ROOT = Path(__file__).parents[2]


def test_lg_rules_cover_all_required_capabilities():
    profile = load_profile("lg-enterprise")
    assert {rule.capability for rule in RULES} == set(profile.required_capabilities)


def test_current_lg_enterprise_conformance_is_evidence_backed_and_passes_required_capabilities():
    profile = load_profile("lg-enterprise")
    report = evaluate(profile, derive_facts(ROOT), facts_source=FACTS_SOURCE)
    by_id = {item.capability: item for item in report.results}

    assert report.overall_status == "PASS"
    assert by_id["risk-issue-management"].status == "PASS"
    assert by_id["effort-estimation"].status == "NOT_APPLICABLE"
    assert all(item.evidence for item in report.results if item.status in {"PASS", "PARTIAL"})
    assert all(item.remediation for item in report.results if item.status in {"PARTIAL", "FAIL"})


def test_missing_repository_root_fails_required_capabilities(tmp_path):
    report = evaluate(load_profile("lg-enterprise"), derive_facts(tmp_path), facts_source=FACTS_SOURCE)
    assert report.overall_status == "FAIL"
    assert any(item.status == "FAIL" for item in report.results if item.requirement == "required")
