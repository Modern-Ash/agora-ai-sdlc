from pathlib import Path

import pytest
import yaml

from agora_ai_sdlc.domain_knowledge import DomainKnowledgeError, parse_descriptor, snapshot

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "domain-knowledge"


def load(name: str):
    return parse_descriptor((FIXTURES / name).read_text(encoding="utf-8"))


def test_local_repository_knowledge_descriptor_is_reference_only():
    source = load("local.yaml")
    assert source.kind == "repository-docs"
    assert source.reference == "repo://docs/domain/payments"
    assert snapshot(source)["content_embedded"] is False


def test_external_wiki_descriptor_is_opaque_and_credential_free():
    source = load("external.yaml")
    assert source.kind == "wiki"
    assert source.reference == "knowledge:wiki/enterprise-architecture"
    assert source.metadata == {"system": "corporate-wiki"}


@pytest.mark.parametrize("kind", ["repository-docs", "wiki", "files", "api", "vector-store"])
def test_all_supported_source_kinds_are_provider_neutral(kind):
    data = yaml.safe_load((FIXTURES / "external.yaml").read_text(encoding="utf-8"))
    data["kind"] = kind
    data["reference"] = f"knowledge:{kind}/source"
    source = parse_descriptor(yaml.safe_dump(data, sort_keys=False))
    assert source.kind == kind


@pytest.mark.parametrize(
    "field",
    ["endpoint", "url", "token", "api_key", "password", "secret", "credentials", "authorization", "headers"],
)
def test_forbidden_credential_and_endpoint_fields_fail_without_echoing_values(field):
    data = yaml.safe_load((FIXTURES / "external.yaml").read_text(encoding="utf-8"))
    secret = "do-not-echo-this-secret"
    data["metadata"][field] = secret

    with pytest.raises(DomainKnowledgeError) as exc:
        parse_descriptor(yaml.safe_dump(data, sort_keys=False))
    assert exc.value.code == "knowledge.forbidden_field"
    assert secret not in str(exc.value)


def test_raw_network_endpoint_is_rejected_but_logical_api_reference_is_allowed():
    data = yaml.safe_load((FIXTURES / "external.yaml").read_text(encoding="utf-8"))
    data["kind"] = "api"
    data["reference"] = "https://corp.example/api/docs"
    with pytest.raises(DomainKnowledgeError) as exc:
        parse_descriptor(yaml.safe_dump(data, sort_keys=False))
    assert exc.value.code == "knowledge.endpoint"

    data["reference"] = "knowledge:api/architecture-catalog"
    assert parse_descriptor(yaml.safe_dump(data, sort_keys=False)).kind == "api"


def test_reference_query_secret_is_rejected_without_echoing_secret():
    data = yaml.safe_load((FIXTURES / "external.yaml").read_text(encoding="utf-8"))
    data["reference"] = "knowledge:wiki/architecture?token=secret-value"
    with pytest.raises(DomainKnowledgeError) as exc:
        parse_descriptor(yaml.safe_dump(data, sort_keys=False))
    assert exc.value.code == "knowledge.reference_secret"
    assert "secret-value" not in str(exc.value)


def test_descriptor_contains_metadata_only_not_content_payload():
    data = yaml.safe_load((FIXTURES / "local.yaml").read_text(encoding="utf-8"))
    data["content"] = "embedded corporate documentation"
    with pytest.raises(DomainKnowledgeError) as exc:
        parse_descriptor(yaml.safe_dump(data, sort_keys=False))
    assert exc.value.code == "knowledge.fields"
