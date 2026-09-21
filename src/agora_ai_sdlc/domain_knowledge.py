"""Provider-neutral domain-knowledge source descriptors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA = "agora-ai-sdlc/domain-knowledge-source/v1"
KINDS = {"repository-docs", "wiki", "files", "api", "vector-store"}
CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
REFERENCE = re.compile(r"^[a-z][a-z0-9+.-]*:[^\s]+$")
FORBIDDEN_FIELDS = {
    "endpoint",
    "url",
    "token",
    "api_key",
    "apikey",
    "password",
    "secret",
    "credential",
    "credentials",
    "authorization",
    "headers",
}


class DomainKnowledgeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class DomainKnowledgeSource:
    id: str
    kind: str
    owner: str
    classification: str
    revision: int
    scope: tuple[str, ...]
    reference: str
    description: str
    metadata: dict[str, str]


def _contains_forbidden_fields(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in FORBIDDEN_FIELDS or _contains_forbidden_fields(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_fields(item) for item in value)
    return False


def parse_descriptor(contents: str) -> DomainKnowledgeSource:
    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as error:
        raise DomainKnowledgeError("knowledge.syntax", "descriptor is not valid YAML") from error
    if not isinstance(data, dict):
        raise DomainKnowledgeError("knowledge.syntax", "descriptor must be a mapping")
    if _contains_forbidden_fields(data):
        raise DomainKnowledgeError("knowledge.forbidden_field", "descriptor contains forbidden credential/endpoint fields")
    expected = {"schema", "id", "kind", "owner", "classification", "revision", "scope", "reference", "description", "metadata"}
    if set(data) != expected:
        raise DomainKnowledgeError("knowledge.fields", "descriptor fields do not match v1 contract")
    if data.get("schema") != SCHEMA:
        raise DomainKnowledgeError("knowledge.schema", f"unsupported schema {data.get('schema')!r}")
    source_id = data.get("id")
    if not isinstance(source_id, str) or SLUG.fullmatch(source_id) is None:
        raise DomainKnowledgeError("knowledge.id", "id must be a provider-neutral lowercase slug")
    kind = data.get("kind")
    if kind not in KINDS:
        raise DomainKnowledgeError("knowledge.kind", f"unsupported source kind {kind!r}")
    owner = data.get("owner")
    if not isinstance(owner, str) or not owner.strip():
        raise DomainKnowledgeError("knowledge.owner", "owner is required")
    classification = data.get("classification")
    if classification not in CLASSIFICATIONS:
        raise DomainKnowledgeError("knowledge.classification", "classification is invalid")
    revision = data.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise DomainKnowledgeError("knowledge.revision", "revision must be a positive integer")
    scope = data.get("scope")
    if not isinstance(scope, list) or not scope or any(not isinstance(item, str) or not item.strip() for item in scope):
        raise DomainKnowledgeError("knowledge.scope", "scope must be a non-empty list of strings")
    if len(set(scope)) != len(scope):
        raise DomainKnowledgeError("knowledge.scope", "scope contains duplicates")
    reference = data.get("reference")
    if not isinstance(reference, str) or REFERENCE.fullmatch(reference) is None:
        raise DomainKnowledgeError("knowledge.reference", "reference must be an opaque logical reference")
    lowered = reference.casefold()
    if any(marker in lowered for marker in ("token=", "password=", "secret=", "api_key=", "apikey=", "authorization=")):
        raise DomainKnowledgeError("knowledge.reference_secret", "reference contains forbidden credential material")
    if reference.startswith(("http:", "https:")):
        raise DomainKnowledgeError("knowledge.endpoint", "raw network endpoints are not allowed; use an opaque source reference")
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        raise DomainKnowledgeError("knowledge.description", "description is required")
    metadata = data.get("metadata")
    if not isinstance(metadata, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()):
        raise DomainKnowledgeError("knowledge.metadata", "metadata must be a string-to-string mapping")
    return DomainKnowledgeSource(
        source_id,
        kind,
        owner.strip(),
        classification,
        revision,
        tuple(item.strip() for item in scope),
        reference,
        description.strip(),
        dict(sorted(metadata.items())),
    )


def load_descriptor(path: Path) -> DomainKnowledgeSource:
    if not path.is_file():
        raise DomainKnowledgeError("knowledge.file", f"descriptor not found: {path}")
    return parse_descriptor(path.read_text(encoding="utf-8"))


def snapshot(source: DomainKnowledgeSource) -> dict:
    return {
        "schema": SCHEMA,
        "id": source.id,
        "kind": source.kind,
        "owner": source.owner,
        "classification": source.classification,
        "revision": source.revision,
        "scope": list(source.scope),
        "reference": source.reference,
        "description": source.description,
        "metadata": source.metadata,
        "content_embedded": False,
    }
