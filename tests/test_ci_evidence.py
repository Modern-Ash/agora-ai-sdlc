import copy
import json
from pathlib import Path

import pytest
from agora.filesystem import packs_root
from agora.tools import load_tool_contract

from agora_ai_sdlc.ci_evidence import (
    CIEvidenceError,
    core_evidence_input,
    evaluate_bundle,
    ingest_evidence,
    load_profile,
    normalize_evidence,
)

FIXTURES = Path(__file__).parents[1] / "samples" / "ci-evidence"
REPOSITORY = "https://github.com/example/product"
COMMIT = "a" * 40


def payloads():
    result = []
    for name in ("github-actions", "gitlab-ci", "jenkins"):
        result.extend(json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8")))
    return result


def normalize(payload):
    environment = "staging" if payload["category"] in {"deployment", "smoke-test"} else "ci"
    return normalize_evidence(
        payload,
        expected_repository=REPOSITORY,
        expected_commit=COMMIT,
        expected_environment=environment,
    )


def bundle(name, facts, environment="ci"):
    return evaluate_bundle(
        name,
        facts,
        expected_repository=REPOSITORY,
        expected_commit=COMMIT,
        expected_environment=environment,
    )


def test_profile_uses_core_neutral_contract_and_equivalent_provider_examples():
    profile = load_profile()
    neutral = load_tool_contract(packs_root() / "tools" / profile["core_tool"])
    assert neutral.id == "ci-cd" and neutral.operations["view-run"].capability == "ci.read"
    assert profile["provider_examples"] == {
        "github-actions": "github-actions/view-run",
        "gitlab-ci": "gitlab-ci/view-run",
        "jenkins": "ci-cd/view-run",
    }
    for adapter in ("github-actions", "gitlab-ci"):
        contract = load_tool_contract(packs_root() / "adapters" / "cli" / adapter)
        assert contract.implements == "ci-cd" and "view-run" in contract.operations


@pytest.mark.parametrize(
    ("status", "allowed", "code"),
    [
        ("success", True, None),
        ("failure", False, "ci.status.failure"),
        ("cancelled", False, "ci.status.cancelled"),
        ("unknown", False, "ci.status.unknown"),
    ],
)
def test_status_matrix(status, allowed, code):
    payload = payloads()[0]
    payload["status"] = status
    fact = normalize(payload)
    assert fact["allowed"] is allowed
    assert ({item["code"] for item in fact["blockers"]} if code else set()) == ({code} if code else set())


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("repository", "https://github.com/other/repository", "ci.repository.mismatch"),
        ("commit", "b" * 40, "ci.commit.stale"),
        ("environment", "production", "ci.environment.mismatch"),
    ],
)
def test_stale_or_mismatched_result_never_satisfies_positive_evidence(field, value, code):
    payload = payloads()[0]
    payload[field] = value
    fact = normalize(payload)
    assert not fact["allowed"]
    assert code in {item["code"] for item in fact["blockers"]}


@pytest.mark.parametrize(
    "reference",
    [
        "http://ci.example.com/run/1",
        "https://user:password@ci.example.com/run/1",
        "https://ci.example.com/run/1?token=secret",
        "https://ci.example.com/run/1#secret",
        "file:///tmp/result.json",
    ],
)
def test_evidence_references_cannot_embed_secrets_or_unbounded_schemes(reference):
    payload = payloads()[0]
    payload["evidence_refs"] = [reference]
    with pytest.raises(CIEvidenceError) as error:
        normalize(payload)
    assert error.value.code == "ci.fact.reference"


def test_evidence_shape_and_reference_count_are_bounded():
    payload = payloads()[0]
    payload["logs"] = "not accepted"
    with pytest.raises(CIEvidenceError) as error:
        normalize(payload)
    assert error.value.code == "ci.fact.fields"
    payload = payloads()[0]
    payload["evidence_refs"] = [f"https://ci.example.com/run/{index}" for index in range(9)]
    with pytest.raises(CIEvidenceError) as error:
        normalize(payload)
    assert error.value.code == "ci.fact.references"


def test_duplicate_ingest_is_idempotent_and_changed_identity_reuse_fails_closed():
    fact = normalize(payloads()[0])
    observations, created = ingest_evidence((), fact)
    repeated, repeated_created = ingest_evidence(observations, copy.deepcopy(fact))
    assert created and not repeated_created and repeated == observations
    changed = copy.deepcopy(fact)
    changed["status"] = "failure"
    changed["fingerprint"] = "sha256:" + "b" * 64
    with pytest.raises(CIEvidenceError) as error:
        ingest_evidence(observations, changed)
    assert error.value.code == "ci.run.conflict"


def test_all_categories_form_three_successful_core_bundles():
    facts = tuple(normalize(payload) for payload in payloads())
    bundles = {
        "test-suite": bundle("test-suite", facts),
        "security-scan": bundle("security-scan", facts),
        "deployment": bundle("deployment", facts, "staging"),
    }
    assert all(bundle["allowed"] for bundle in bundles.values())
    assert bundles["test-suite"]["categories"] == ("build", "unit", "integration", "quality")
    assert bundles["security-scan"]["categories"] == ("security",)
    assert bundles["deployment"]["categories"] == ("deployment", "smoke-test")
    core = core_evidence_input(
        bundles["test-suite"],
        swarm_id="delivery",
        work_id="feature",
        actor_id="builder",
    )
    assert core.type == "test-suite" and core.result == "success"
    assert core.tested_commit == COMMIT and core.environment == "ci" and core.dedupe_key


def test_missing_or_non_success_category_blocks_bundle_and_maps_to_core_failure():
    facts = tuple(normalize(payload) for payload in payloads() if payload["category"] != "unit")
    result = bundle("test-suite", facts)
    assert not result["allowed"] and result["blockers"][0]["code"] == "ci.bundle.missing"
    core = core_evidence_input(
        result,
        swarm_id="delivery",
        work_id="feature",
        actor_id="builder",
    )
    assert core.result == "failure"


def test_bundle_cannot_mix_individually_valid_facts_from_different_contexts():
    raw = payloads()
    unit = next(payload for payload in raw if payload["category"] == "unit")
    unit["repository"] = "https://github.com/other/repository"
    facts = [normalize(payload) for payload in raw if payload["category"] != "unit"]
    facts.append(
        normalize_evidence(
            unit,
            expected_repository=unit["repository"],
            expected_commit=COMMIT,
            expected_environment="ci",
        )
    )
    result = bundle("test-suite", facts)
    assert not result["allowed"]
    assert result["blockers"][0] == {
        "code": "ci.bundle.missing",
        "message": "no successful current unit evidence",
    }


def test_invalid_status_category_commit_and_bundle_are_rejected():
    cases = [
        ("status", "passed", "ci.fact.status"),
        ("category", "e2e", "ci.fact.category"),
        ("commit", "abc123", "ci.fact.commit"),
    ]
    for field, value, code in cases:
        payload = payloads()[0]
        payload[field] = value
        with pytest.raises(CIEvidenceError) as error:
            normalize(payload)
        assert error.value.code == code
    with pytest.raises(CIEvidenceError) as error:
        bundle("release", ())
    assert error.value.code == "ci.bundle.unknown"
