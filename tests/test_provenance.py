import copy
import itertools

import pytest

from agora_ai_sdlc.provenance import DIMENSIONS, ProvenanceError, compare, evaluate_separation, parse


def val(value, source="declared"):
    return {"value": value, "source": source}


def rec(actor="a", runtime="codex", provider="provider-a", model="m1", source="declared", **extra):
    data = {
        "schema": "agora-ai-sdlc/provenance/v1", "actor": actor,
        "runtime": val(runtime, source), "provider": val(provider, source), "model": val(model, source),
        "runtime_version": {"source": "unavailable"}, "selection_reason": val("default", "declared"),
    }  # fmt: skip
    data.update(extra)
    return data


def code(record):
    with pytest.raises(ProvenanceError) as exc:
        parse(record)
    return exc.value.code


def test_valid_record_parses_with_sources():
    p = parse(rec())
    assert p.provider.value == "provider-a" and p.provider.source == "declared"
    assert p.runtime_version.source == "unavailable" and p.runtime_version.value is None


def test_missing_fields_default_to_unavailable():
    r = rec()
    del r["runtime_version"], r["selection_reason"]
    p = parse(r)
    assert p.runtime_version.source == "unavailable" and p.selection_reason.source == "unavailable"


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda r: r.update(schema="x"), "provenance.schema"),
        (lambda r: r.update(extra_field=1), "provenance.unknown_field"),
        (lambda r: r.update(actor=""), "provenance.actor"),
        (lambda r: r.update(provider={"value": "p", "source": "guess"}), "provenance.source"),
        (lambda r: r.update(provider={"value": "p"}), "provenance.field"),
        (lambda r: r.update(provider={"value": "", "source": "declared"}), "provenance.value"),
        (lambda r: r.update(provider={"value": "p", "source": "unavailable"}), "provenance.unavailable_value"),
        (lambda r: r.update(fallback={"used": True}), "provenance.fallback"),
        (lambda r: r.update(fallback={"used": True, "from": {"provider": "p", "model": "m"}}), "provenance.fallback"),
        (lambda r: r.update(subject={"kind": "architecture"}), "provenance.subject"),
        (
            lambda r: r.update(subject={"kind": "architecture", "id": "ARC-001", "revision": 0, "digest": "x"}),
            "provenance.subject",
        ),
    ],
)
def test_invalid_records(mutate, expected):
    r = rec()
    mutate(r)
    assert code(r) == expected


def test_valid_fallback_metadata():
    p = parse(rec(fallback={"used": True, "from": {"provider": "p", "model": "m"}, "reason": "quota"}))
    assert p.fallback_used and p.fallback_from == {"provider": "p", "model": "m"} and p.fallback_reason == "quota"


def test_valid_subject_binding_is_normalized():
    p = parse(
        rec(
            subject={
                "kind": " architecture ",
                "id": " ARC-001 ",
                "revision": 2,
                "digest": " sha256:x ",
            }
        )
    )
    assert p.subject == {"kind": "architecture", "id": "ARC-001", "revision": 2, "digest": "sha256:x"}


@pytest.mark.parametrize("key", ["api_key", "token", "password", "endpoint", "base_url", "Authorization", "secret"])
def test_secret_looking_fields_rejected(key):
    assert code(rec(**{key: "x"})) in {"provenance.secret", "provenance.unknown_field"}
    r = rec()
    r["runtime"] = {"value": "codex", "source": "declared", key: "x"}
    assert code(r) == "provenance.secret"


@pytest.mark.parametrize(
    "value",
    [
        "sk-abcdefgh1234",
        "Bearer abc.def",
        "https://user:pw@host/x",
        "http://localhost:11434",
        "ghp_abcdefghij12",
        "AKIAABCDEFGHIJKLMNOP",
    ],
)
def test_secret_looking_values_rejected(value):
    r = rec()
    r["selection_reason"] = val(value)
    assert code(r) == "provenance.secret"


def test_local_and_internal_providers_need_no_special_case():
    for provider in ("local", "internal-gateway", "ollama-localhost"):
        assert parse(rec(provider=provider)).provider.value == provider


def test_unknown_never_distinct_at_every_dimension():
    a, unknown = parse(rec()), parse(rec(provider="x"))
    unavailable = rec()
    for name in ("runtime", "provider", "model"):
        unavailable[name] = {"source": "unavailable"}
    u = parse(unavailable)
    for dim in ("runtime", "provider", "model"):
        assert compare(a, u, dim) == "unknown" and compare(u, a, dim) == "unknown" and compare(u, u, dim) == "unknown"
    assert compare(a, unknown, "provider") == "distinct"


def test_min_source_observed_rejects_declared():
    declared, observed = parse(rec(provider="x")), parse(rec(provider="y", source="observed"))
    assert compare(declared, observed, "provider", "declared") == "distinct"
    assert compare(declared, observed, "provider", "observed") == "unknown"
    with pytest.raises(ProvenanceError):
        compare(declared, observed, "provider", "guess")
    with pytest.raises(ProvenanceError):
        compare(declared, observed, "colour")


def test_model_name_does_not_imply_provider():
    a = parse(rec(provider="provider-a", model="shared-model"))
    b = parse(rec(provider="provider-b", model="shared-model"))
    assert compare(a, b, "model") == "same" and compare(a, b, "provider") == "distinct"
    same_provider = parse(rec(provider="provider-a", model="other"))
    assert compare(a, same_provider, "provider") == "same"


def test_comparison_normalizes_case_and_whitespace_and_is_symmetric():
    a, b = parse(rec(provider=" Provider-A ")), parse(rec(provider="provider-a"))
    assert compare(a, b, "provider") == "same" == compare(b, a, "provider")


def test_actor_dimension_uses_identity():
    assert compare(parse(rec(actor="x")), parse(rec(actor="X")), "actor") == "same"
    assert compare(parse(rec(actor="x")), parse(rec(actor="y")), "actor") == "distinct"


def test_separation_all_dimension_combinations_deterministic():
    producer = parse(rec(actor="p", runtime="r1", provider="v1", model="m1"))
    reviewer = parse(rec(actor="q", runtime="r2", provider="v1", model="m2"))  # provider is shared
    for size in range(1, 5):
        for dims in itertools.combinations(DIMENSIONS, size):
            first = evaluate_separation(list(dims), producer, reviewer)
            assert first == evaluate_separation(list(reversed(dims)), producer, reviewer)
            assert first["allowed"] == ("provider" not in dims)
            assert [b["dimension"] for b in first["blockers"]] == (["provider"] if "provider" in dims else [])


def test_blockers_are_actionable_and_distinguish_same_from_unknown():
    producer = parse(rec())
    unknown = rec()
    unknown["provider"] = {"source": "unavailable"}
    result = evaluate_separation(["actor", "provider"], producer, parse(unknown))
    by_dim = {b["dimension"]: b for b in result["blockers"]}
    assert by_dim["actor"]["status"] == "same" and "different actor" in by_dim["actor"]["message"]
    assert by_dim["provider"]["status"] == "unknown" and "not distinct" in by_dim["provider"]["message"]
    assert not result["allowed"]


def test_input_is_not_mutated():
    r = rec()
    snapshot = copy.deepcopy(r)
    parse(r)
    assert r == snapshot
