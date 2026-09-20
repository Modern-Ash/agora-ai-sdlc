import itertools
from types import SimpleNamespace

import pytest

from agora_ai_sdlc.data_classification import (
    CLASSIFICATIONS,
    EXECUTION_BOUNDARIES,
    ClassifiedInput,
    DataPolicy,
    RuntimeEligibility,
    evaluate_launch,
    validate_authorization,
)
from agora_ai_sdlc.provenance import Value, parse


def provenance(runtime="runtime-a", source="declared"):
    def value(item):
        return {"value": item, "source": source}

    return parse(
        {
            "schema": "agora-ai-sdlc/provenance/v1",
            "actor": "worker",
            "runtime": value(runtime),
            "runtime_version": {"source": "unavailable"},
            "provider": value("provider-a"),
            "model": value("model-a"),
            "selection_reason": value("policy eligible"),
        }
    )


def eligibility(max_classification="restricted", boundaries=("local",), revision=1, evidence="EV-001"):
    return RuntimeEligibility("runtime-a", max_classification, boundaries, revision, evidence)


def item(classification, revision=1, input_id="INPUT-001"):
    return ClassifiedInput(input_id, classification, revision)


def evaluate(inputs, *, eligible=None, boundary="local", boundary_source="declared", policy=None):
    return evaluate_launch(
        inputs=inputs,
        runtime=provenance(),
        execution_boundary=Value(boundary, boundary_source),
        eligibility=eligible or eligibility(),
        policy=policy,
    )


@pytest.mark.parametrize(("input_classification", "maximum"), list(itertools.product(CLASSIFICATIONS, repeat=2)))
def test_classification_eligibility_matrix(input_classification, maximum):
    result = evaluate([item(input_classification)], eligible=eligibility(maximum))
    assert result["allowed"] == (CLASSIFICATIONS.index(input_classification) <= CLASSIFICATIONS.index(maximum))


@pytest.mark.parametrize("boundary", EXECUTION_BOUNDARIES)
def test_execution_boundary_eligibility_matrix(boundary):
    allowed = ("local", "customer-controlled")
    result = evaluate([item("internal")], eligible=eligibility(boundaries=allowed), boundary=boundary)
    assert result["allowed"] == (boundary in allowed)


def test_restricted_content_is_blocked_for_external_ineligible_runtime():
    result = evaluate(
        [item("restricted", input_id="customer-records")],
        eligible=eligibility("confidential", boundaries=("external",)),
        boundary="external",
    )
    assert not result["allowed"]
    assert result["offending_inputs"] == ("customer-records",)
    assert {blocker["code"] for blocker in result["blockers"]} == {"classification.exceeds_runtime"}


def test_effective_classification_uses_most_restrictive_referenced_input():
    result = evaluate(
        [item("public", input_id="a"), item("confidential", input_id="b"), item("internal", input_id="c")]
    )
    assert result["allowed"] and result["effective_classification"] == "confidential"


def test_unknown_classification_fails_closed_by_default():
    result = evaluate([item(None, input_id="unknown-input")])
    assert not result["allowed"]
    assert result["offending_inputs"] == ("unknown-input",)
    assert result["blockers"][0]["code"] == "classification.unknown"


@pytest.mark.parametrize(("default", "allowed"), [("restricted", False), ("public", True)])
def test_unknown_classification_default_is_configurable(default, allowed):
    result = evaluate(
        [item(None)],
        eligible=eligibility("confidential"),
        policy=DataPolicy(unknown_default=default),
    )
    assert result["allowed"] is allowed
    assert result["effective_classification"] == default


def test_runtime_identity_boundary_and_evidence_must_be_proven():
    missing_runtime = evaluate_launch(
        inputs=[item("public")],
        runtime=provenance(source="declared"),
        execution_boundary=Value("local", "declared"),
        eligibility=eligibility(evidence=""),
        policy=DataPolicy(min_runtime_source="observed", min_boundary_source="observed"),
    )
    assert {blocker["code"] for blocker in missing_runtime["blockers"]} == {
        "runtime.eligibility.evidence",
        "runtime.identity.unproven",
        "runtime.boundary.unproven",
    }


def test_errors_identify_inputs_without_content():
    sensitive_content = "customer SSN 123-45-6789"
    input_with_content = SimpleNamespace(
        id="customer-file",
        classification=sensitive_content,
        revision=1,
        content=sensitive_content,
    )
    result = evaluate(
        [input_with_content],
        eligible=eligibility("public"),
    )
    rendered = repr(result)
    assert "customer-file" in rendered
    assert sensitive_content not in rendered


@pytest.mark.parametrize(
    "changed_inputs",
    [
        [item("confidential", revision=1)],
        [item("internal", revision=2)],
    ],
)
def test_classification_or_revision_change_makes_authorization_stale(changed_inputs):
    original_inputs = [item("internal", revision=1)]
    authorization = evaluate(original_inputs)["authorization"]
    result = validate_authorization(
        authorization,
        inputs=changed_inputs,
        runtime=provenance(),
        execution_boundary=Value("local", "declared"),
        eligibility=eligibility(),
    )
    assert not result["allowed"]
    assert result["blockers"][0]["code"] == "authorization.stale"


def test_eligibility_revision_change_makes_authorization_stale():
    inputs = [item("internal")]
    authorization = evaluate(inputs)["authorization"]
    result = validate_authorization(
        authorization,
        inputs=inputs,
        runtime=provenance(),
        execution_boundary=Value("local", "declared"),
        eligibility=eligibility(revision=2),
    )
    assert not result["allowed"]
    assert result["blockers"][0]["code"] == "authorization.stale"
