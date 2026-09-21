import json
from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.compatibility_profiles import load_profile
from agora_ai_sdlc.conformance.compatibility import (
    FACTS_SCHEMA,
    RESULT_SCHEMA,
    CapabilityFact,
    ConformanceError,
    evaluate,
    evaluate_project,
    parse_facts,
    render_human,
)

ROOT = Path(__file__).parents[2]


def fact(capability, status="PASS", *, reason="verified", evidence=None, remediation=None):
    return CapabilityFact(
        capability=capability,
        status=status,
        evidence=tuple(evidence or [f"repo://evidence/{capability}.md"]),
        reason=reason,
        remediation=remediation,
    )


def all_required(profile):
    return tuple(fact(capability) for capability in profile.required_capabilities)


def write_facts(path, facts):
    data = {
        "schema": FACTS_SCHEMA,
        "facts": [
            {
                "capability": item.capability,
                "status": item.status,
                "evidence": list(item.evidence),
                "reason": item.reason,
                **({"remediation": item.remediation} if item.remediation is not None else {}),
            }
            for item in facts
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_required_pass_optional_missing_and_result_order_are_deterministic():
    profile = load_profile("aws-original")
    report = evaluate(profile, tuple(reversed(all_required(profile))), facts_source="facts.yaml")

    assert report.overall_status == "PASS"
    assert not report.has_failures
    required = [item for item in report.results if item.requirement == "required"]
    optional = [item for item in report.results if item.requirement == "optional"]
    assert [item.capability for item in required] == sorted(profile.required_capabilities)
    assert {item.status for item in required} == {"PASS"}
    assert {item.status for item in optional} == {"NOT_APPLICABLE"}
    assert all(item.source_contract_version == profile.version for item in report.results)
    assert report.snapshot()["schema"] == RESULT_SCHEMA


def test_missing_required_fails_closed_with_remediation():
    profile = load_profile("aws-original")
    report = evaluate(profile, ())

    assert report.overall_status == "FAIL" and report.has_failures
    required = [item for item in report.results if item.requirement == "required"]
    assert required and {item.status for item in required} == {"FAIL"}
    assert all(item.reason == "No project capability fact was supplied." for item in required)
    assert all(item.remediation for item in required)


def test_partial_and_fail_facts_drive_overall_status_and_default_remediation():
    profile = load_profile("aws-original")
    facts = list(all_required(profile))
    facts[0] = fact(facts[0].capability, "PARTIAL", reason="some evidence")
    partial = evaluate(profile, tuple(facts))
    assert partial.overall_status == "PARTIAL"
    assert next(item for item in partial.results if item.capability == facts[0].capability).remediation

    facts[1] = fact(facts[1].capability, "FAIL", reason="control absent", evidence=[])
    failed = evaluate(profile, tuple(facts))
    assert failed.overall_status == "FAIL" and failed.has_failures


def test_explicit_not_applicable_fact_is_preserved_for_declared_capability():
    profile = load_profile("aws-original")
    facts = list(all_required(profile))
    target = facts[0].capability
    facts[0] = fact(target, "NOT_APPLICABLE", reason="not relevant for this project", evidence=[])
    report = evaluate(profile, tuple(facts))
    result = next(item for item in report.results if item.capability == target)
    assert result.status == "NOT_APPLICABLE"
    assert result.remediation is None


def test_unknown_capability_fact_is_rejected():
    profile = load_profile("aws-original")
    with pytest.raises(ConformanceError) as exc:
        evaluate(profile, (fact("not-in-profile"),))
    assert exc.value.code == "conformance.fact_unknown_capability"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"schema": "wrong", "facts": []}, "conformance.fact_schema"),
        ({"schema": FACTS_SCHEMA, "facts": [{"capability": "x", "status": "MAYBE", "reason": "x"}]}, "conformance.fact_status"),
        (
            {
                "schema": FACTS_SCHEMA,
                "facts": [
                    {"capability": "x", "status": "PASS", "reason": "x"},
                    {"capability": "x", "status": "PASS", "reason": "again"},
                ],
            },
            "conformance.fact_duplicate",
        ),
        ({"schema": FACTS_SCHEMA, "facts": [{"capability": "x", "status": "PASS"}]}, "conformance.fact_missing"),
        (
            {
                "schema": FACTS_SCHEMA,
                "facts": [{"capability": "x", "status": "PASS", "reason": "x", "evidence": ["a", "a"]}],
            },
            "conformance.fact_duplicate_evidence",
        ),
    ],
)
def test_invalid_fact_contracts_fail_with_stable_codes(payload, expected):
    with pytest.raises(ConformanceError) as exc:
        parse_facts(yaml.safe_dump(payload))
    assert exc.value.code == expected


def test_project_default_fact_discovery_and_explicit_missing_path(tmp_path):
    profile = load_profile("aws-original")
    default = tmp_path / ".agora" / "ai-sdlc" / "conformance-facts.yaml"
    write_facts(default, all_required(profile))

    report = evaluate_project("aws-original", project_root=tmp_path)
    assert report.overall_status == "PASS"
    assert report.facts_source == str(default)

    with pytest.raises(ConformanceError) as exc:
        evaluate_project("aws-original", project_root=tmp_path, facts_path=tmp_path / "missing.yaml")
    assert exc.value.code == "conformance.fact_file"


def test_missing_default_facts_is_valid_report_that_fails_required_capabilities(tmp_path):
    report = evaluate_project("aws-original", project_root=tmp_path)
    assert report.overall_status == "FAIL"
    assert report.facts_source is None


def test_unknown_profile_is_normalized_to_conformance_error():
    with pytest.raises(ConformanceError) as exc:
        evaluate_project("missing-profile")
    assert exc.value.code == "conformance.profile"


def test_human_render_contains_reason_evidence_remediation_and_contract():
    profile = load_profile("aws-original")
    facts = list(all_required(profile))
    facts[0] = fact(facts[0].capability, "PARTIAL", reason="incomplete", remediation="finish it")
    text = render_human(evaluate(profile, tuple(facts), facts_source="facts.yaml"))
    assert "Overall: PARTIAL" in text
    assert "reason: incomplete" in text
    assert "remediation: finish it" in text
    assert f"contract: {profile.version}" in text
    assert "Facts: facts.yaml" in text


def test_checked_in_json_schemas_match_runtime_contracts():
    facts_schema = json.loads(
        (ROOT / "contracts" / "conformance" / "conformance-facts-v1.schema.json").read_text(encoding="utf-8")
    )
    result_schema = json.loads(
        (ROOT / "contracts" / "conformance" / "conformance-result-v1.schema.json").read_text(encoding="utf-8")
    )
    assert facts_schema["properties"]["schema"]["const"] == FACTS_SCHEMA
    assert result_schema["properties"]["schema"]["const"] == RESULT_SCHEMA
    assert result_schema["properties"]["overall_status"]["enum"] == [
        "PASS",
        "PARTIAL",
        "FAIL",
        "NOT_APPLICABLE",
    ]
    assert "source_contract_version" in result_schema["properties"]["results"]["items"]["properties"]
