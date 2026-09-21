import json
from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.compatibility_profiles import load_profile
from agora_ai_sdlc.conformance.aws_original import (
    RULES_SCHEMA,
    AwsOriginalRuleError,
    derive_additive_governance,
    derive_facts,
    load_rules,
    parse_rules,
)
from agora_ai_sdlc.conformance.compatibility import evaluate

ROOT = Path(__file__).parents[2]
GOLDEN = ROOT / "tests" / "fixtures" / "conformance" / "aws-original" / "current.yaml"


def grouped(report):
    groups = {"PASS": [], "PARTIAL": [], "FAIL": [], "NOT_APPLICABLE": []}
    for item in report.results:
        groups[item.status].append(item.capability)
    return {status: sorted(values) for status, values in groups.items()}


def test_rules_cover_every_declared_profile_capability_and_separate_additive_governance():
    profile = load_profile("aws-original")
    rules = load_rules()
    base = {rule.capability for rule in rules.base_rules}
    declared = set(profile.required_capabilities) | set(profile.optional_capabilities) | set(profile.unsupported_capabilities)

    assert base == declared
    assert {rule.classification for rule in rules.base_rules} == {"base-method"}
    assert {rule.classification for rule in rules.additive_governance} == {"agora-additive"}
    additive = {rule.id for rule in rules.additive_governance}
    assert additive
    assert additive.isdisjoint(declared)


def test_current_repository_matches_pass_partial_fail_golden():
    expected = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    profile = load_profile("aws-original")
    facts = derive_facts(ROOT)
    report = evaluate(profile, facts, facts_source="derived:aws-original-rules/v1")

    assert profile.version == expected["profile_version"]
    assert grouped(report) == {status: sorted(values) for status, values in expected["expected"].items()}
    assert report.overall_status == "FAIL"


def test_each_fact_has_explicit_repository_evidence_or_actionable_remediation():
    facts = derive_facts(ROOT)
    assert facts
    for item in facts:
        if item.status == "PASS":
            assert item.evidence
            assert item.remediation is None
        else:
            assert item.remediation


def test_additive_governance_is_reported_but_never_scored_as_base_method():
    profile = load_profile("aws-original")
    report = evaluate(profile, derive_facts(ROOT))
    scored = {item.capability for item in report.results}
    additive = derive_additive_governance(ROOT)

    assert additive
    assert {item.id for item in additive}.isdisjoint(scored)
    assert {item.status for item in additive} == {"PASS"}
    assert all(item.snapshot()["classification"] == "agora-additive" for item in additive)


def test_rules_contract_schema_matches_runtime():
    schema = json.loads(
        (ROOT / "contracts" / "conformance" / "aws-original-rules-v1.schema.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema"]["const"] == RULES_SCHEMA
    assert schema["properties"]["id"]["const"] == "aws-original"
    assert schema["properties"]["profile"]["const"] == "aws-original"


def test_unknown_check_type_fails_with_stable_code():
    raw = yaml.safe_load(
        (ROOT / "contracts" / "conformance" / "aws-original-rules-v1.yaml").read_text(encoding="utf-8")
    )
    raw["base_rules"][0]["pass"][0]["type"] = "magic"
    with pytest.raises(AwsOriginalRuleError) as exc:
        parse_rules(yaml.safe_dump(raw, sort_keys=False))
    assert exc.value.code == "aws-rule.check_type"


def test_missing_rule_for_profile_capability_fails_closed():
    raw = yaml.safe_load(
        (ROOT / "contracts" / "conformance" / "aws-original-rules-v1.yaml").read_text(encoding="utf-8")
    )
    raw["base_rules"] = raw["base_rules"][1:]
    with pytest.raises(AwsOriginalRuleError) as exc:
        parse_rules(yaml.safe_dump(raw, sort_keys=False))
    assert exc.value.code == "aws-rule.missing"


def test_rule_for_undeclared_capability_is_rejected():
    raw = yaml.safe_load(
        (ROOT / "contracts" / "conformance" / "aws-original-rules-v1.yaml").read_text(encoding="utf-8")
    )
    clone = dict(raw["base_rules"][0])
    clone["capability"] = "not-declared"
    raw["base_rules"].append(clone)
    with pytest.raises(AwsOriginalRuleError) as exc:
        parse_rules(yaml.safe_dump(raw, sort_keys=False))
    assert exc.value.code == "aws-rule.undeclared"


def test_rule_paths_cannot_escape_repository_root():
    raw = yaml.safe_load(
        (ROOT / "contracts" / "conformance" / "aws-original-rules-v1.yaml").read_text(encoding="utf-8")
    )
    raw["base_rules"][0]["evidence"] = ["../outside"]
    with pytest.raises(AwsOriginalRuleError) as exc:
        parse_rules(yaml.safe_dump(raw, sort_keys=False))
    assert exc.value.code == "aws-rule.path"


def test_derivation_is_offline(monkeypatch):
    import socket
    import urllib.request

    def blocked(*_args, **_kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)

    facts = derive_facts(ROOT)
    assert facts
