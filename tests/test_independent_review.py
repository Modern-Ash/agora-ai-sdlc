import itertools
from pathlib import Path

import pytest

from agora_ai_sdlc.artifacts import parse_template
from agora_ai_sdlc.independent_review import (
    CRITICAL_ARTIFACT_KINDS,
    PROFILES,
    ArtifactRevision,
    Review,
    ReviewPolicyError,
    Waiver,
    artifact_revision,
    check_critical_artifact_policy,
    evaluate_review,
    resolve_profiles,
)
from agora_ai_sdlc.provenance import parse

ROOT = Path(__file__).parent.parent
TEMPLATES = ROOT / "templates"


def val(value, source="declared"):
    return {"value": value, "source": source}


def prov(actor, runtime="codex", provider="provider-a", model="m1", source="declared", item=None):
    record = {
        "schema": "agora-ai-sdlc/provenance/v1",
        "actor": actor,
        "runtime": val(runtime, source),
        "provider": val(provider, source),
        "model": val(model, source),
        "runtime_version": {"source": "unavailable"},
        "selection_reason": val("test", "declared"),
    }
    if item is not None:
        record["subject"] = {
            "kind": item.kind,
            "id": item.id,
            "revision": item.revision,
            "digest": item.digest,
        }
    return parse(record)


def prov_unknown_provider(actor):
    record = {
        "schema": "agora-ai-sdlc/provenance/v1",
        "actor": actor,
        "runtime": val("codex"),
        "provider": {"source": "unavailable"},
        "model": val("m1"),
        "runtime_version": {"source": "unavailable"},
        "selection_reason": val("test", "declared"),
    }
    return parse(record)


def subject(policy=("distinct-actor",), revision=1, digest="sha256:abc"):
    return ArtifactRevision("architecture", "ARC-001", revision, digest, tuple(policy))


def review_for(
    item, actor="reviewer", actor_kind="human", provider="provider-b", source="declared", verdict="approved"
):
    return Review(
        actor=actor,
        actor_kind=actor_kind,
        role="quality-reviewer",
        subject=item,
        verdict=verdict,
        provenance=prov(actor, provider=provider, source=source),
    )


def review_with_provenance(item, provenance, actor_kind="human", verdict="approved"):
    return Review(
        actor=provenance.actor,
        actor_kind=actor_kind,
        role="quality-reviewer",
        subject=item,
        verdict=verdict,
        provenance=provenance,
    )


def codes(result):
    return {b["code"] for b in result["blockers"]}


def test_all_profile_combinations_resolve_deterministically():
    names = sorted(PROFILES)
    for size in range(1, len(names) + 1):
        for combo in itertools.combinations(names, size):
            forward = resolve_profiles(combo)
            backward = resolve_profiles(reversed(combo))
            assert forward == backward

            item = subject(policy=combo)
            producer = prov("producer", runtime="r1", provider="p1", model="m1", source="observed", item=item)
            reviewer = review_with_provenance(
                item,
                prov("reviewer", runtime="r2", provider="p2", model="m2", source="observed"),
            )
            assert evaluate_review(produced=item, producer=producer, review=reviewer)["allowed"]


def test_profile_dimensions_block_self_review_or_ambiguous_provenance():
    item = subject(policy=("distinct-actor", "distinct-provider"))
    producer = prov("same", provider="provider-a", item=item)
    same_actor = review_for(item, actor="same", provider="provider-b")
    same_provider = review_for(item, actor="other", provider="provider-a")
    assert "review.separation.actor" in codes(evaluate_review(produced=item, producer=producer, review=same_actor))
    assert "review.separation.provider" in codes(
        evaluate_review(produced=item, producer=producer, review=same_provider)
    )
    assert "review.separation.provider" in codes(
        evaluate_review(
            produced=item, producer=producer, review=review_with_provenance(item, prov_unknown_provider("other"))
        )
    )
    assert evaluate_review(produced=item, producer=producer, review=review_for(item))["allowed"]


def test_observed_regulated_profile_treats_declared_values_as_ambiguous():
    item = subject(policy=("regulated",))
    result = evaluate_review(produced=item, producer=prov("p", item=item), review=review_for(item, actor="q"))
    assert not result["allowed"]
    assert "review.separation.provider" in codes(result)


def test_stale_review_when_artifact_revision_or_digest_changes():
    produced = subject(revision=2, digest="sha256:new")
    old_review = review_for(subject(revision=1, digest="sha256:old"))
    result = evaluate_review(produced=produced, producer=prov("builder", item=produced), review=old_review)
    assert "review.stale" in codes(result)


def test_authorized_waiver_requires_actor_reason_and_evidence():
    item = subject(policy=("distinct-provider",))
    producer = prov("builder", provider="provider-a", item=item)
    review = review_for(item, actor="reviewer", provider="provider-a")
    waiver = Waiver(actor="owner", role="governance-owner", reason="temporary reviewer shortage", evidence="EV-001")
    result = evaluate_review(produced=item, producer=producer, review=review, waiver=waiver)
    assert result["allowed"] and [w["code"] for w in result["waived"]] == ["review.separation.provider"]


@pytest.mark.parametrize("field", ["actor", "reason", "evidence"])
def test_incomplete_waiver_fails_closed(field):
    item = subject(policy=("distinct-provider",))
    values = {
        "actor": "owner",
        "role": "governance-owner",
        "reason": "temporary shortage",
        "evidence": "EV-001",
    }
    values[field] = ""
    result = evaluate_review(
        produced=item,
        producer=prov("builder", provider="provider-a", item=item),
        review=review_for(item, actor="reviewer", provider="provider-a"),
        waiver=Waiver(**values),
    )
    assert {f"review.waiver.{field}", "review.separation.provider"} <= codes(result)


def test_unauthorized_waiver_does_not_clear_policy_blocker():
    item = subject(policy=("distinct-provider",))
    result = evaluate_review(
        produced=item,
        producer=prov("builder", provider="provider-a", item=item),
        review=review_for(item, actor="reviewer", provider="provider-a"),
        waiver=Waiver(actor="reviewer", role="quality-reviewer", reason="same stack", evidence="EV-001"),
    )
    assert {"review.waiver.role", "review.separation.provider"} <= codes(result)


def test_regulated_profile_cannot_waive_required_human_final_approval():
    item = subject(policy=("regulated",))
    waiver = Waiver(actor="owner", role="governance-owner", reason="emergency", evidence="EV-002")
    result = evaluate_review(
        produced=item,
        producer=prov("builder", provider="provider-a", source="observed", item=item),
        review=review_for(item, actor="reviewer", actor_kind="ai-agent", provider="provider-b", source="observed"),
        waiver=waiver,
    )
    assert "review.waiver.human_final" in codes(result)


def test_producer_and_reviewer_provenance_must_match_their_bound_identity():
    item = subject()
    unbound = evaluate_review(produced=item, producer=prov("builder"), review=review_for(item))
    assert "review.production_subject" in codes(unbound)

    original = review_for(item)
    mismatched_review = Review(
        actor="someone-else",
        actor_kind=original.actor_kind,
        role=original.role,
        subject=original.subject,
        verdict=original.verdict,
        provenance=original.provenance,
    )
    result = evaluate_review(
        produced=item,
        producer=prov("builder", item=item),
        review=mismatched_review,
    )
    assert "review.provenance.actor" in codes(result)


def test_critical_templates_declare_applicable_separation_policy():
    for path in sorted(TEMPLATES.glob("*.md")):
        if path.name == "README.md":
            continue
        artifact = parse_template(path.read_text())
        if artifact.kind in CRITICAL_ARTIFACT_KINDS:
            check_critical_artifact_policy(artifact)


def test_artifact_revision_requires_policy_and_positive_revision():
    artifact = parse_template((TEMPLATES / "architecture.md").read_text())
    bad = artifact.front | {"separation-policy": []}
    with pytest.raises(ReviewPolicyError) as exc:
        artifact_revision(artifact.__class__(**{**artifact.__dict__, "front": bad}), "sha256:abc")
    assert exc.value.code == "review.policy"
