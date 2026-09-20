"""Runtime, provider and model provenance: validation and deterministic separation comparison.

Every value is `observed` (measured by the platform), `declared` (asserted by a configuration or an actor) or
`unavailable`. Unknown provenance never counts as distinct. Credentials and endpoints are never accepted.
"""

import re
from dataclasses import dataclass

SCHEMA = "agora-ai-sdlc/provenance/v1"
SOURCES = ("observed", "declared", "unavailable")
RANK = {"observed": 2, "declared": 1, "unavailable": 0}
FIELDS = ("runtime", "runtime_version", "provider", "model", "selection_reason")
DIMENSIONS = ("actor", "runtime", "provider", "model")
TOP = {"schema", "actor", "subject", *FIELDS, "fallback"}
SUBJECT_FIELDS = {"kind", "id", "revision", "digest"}
SECRET_KEY = re.compile(
    r"secret|token|password|passwd|credential|api[_-]?key|authorization|endpoint|url|private", re.IGNORECASE
)
SECRET_VALUE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|bearer\s+\S+|://[^/\s:@]+:[^/\s@]+@|https?://|-----BEGIN|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{10,})",
    re.IGNORECASE,
)


class ProvenanceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Value:
    value: str | None
    source: str


@dataclass(frozen=True)
class Provenance:
    actor: str
    runtime: Value
    runtime_version: Value
    provider: Value
    model: Value
    selection_reason: Value
    fallback_used: bool
    fallback_from: dict[str, str] | None
    fallback_reason: str | None
    subject: dict | None


def _scan(node, path: str) -> None:
    if isinstance(node, dict):
        for key, child in node.items():
            if SECRET_KEY.search(str(key)):
                raise ProvenanceError("provenance.secret", f"field {path}{key!r} looks like a credential or endpoint")
            _scan(child, f"{path}{key}.")
    elif isinstance(node, list):
        for child in node:
            _scan(child, path)
    elif isinstance(node, str) and SECRET_VALUE.search(node):
        raise ProvenanceError("provenance.secret", f"value at {path.rstrip('.')} looks like a credential or endpoint")


def _value(record: dict, name: str) -> Value:
    raw = record.get(name)
    if raw is None:
        return Value(None, "unavailable")
    if not isinstance(raw, dict) or set(raw) - {"value", "source"} or "source" not in raw:
        raise ProvenanceError("provenance.field", f"{name!r} must be an object with 'source' and optional 'value'")
    source, value = raw["source"], raw.get("value")
    if source not in SOURCES:
        raise ProvenanceError("provenance.source", f"{name!r} source {source!r} must be one of {', '.join(SOURCES)}")
    if source == "unavailable":
        if value is not None:
            raise ProvenanceError("provenance.unavailable_value", f"{name!r} is unavailable and must not carry a value")
        return Value(None, source)
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceError("provenance.value", f"{name!r} needs a non-empty string value when {source}")
    return Value(value.strip(), source)


def _subject(record: dict) -> dict | None:
    subject = record.get("subject")
    if subject is None:
        return None
    if not isinstance(subject, dict) or set(subject) != SUBJECT_FIELDS:
        raise ProvenanceError(
            "provenance.subject",
            "subject must contain exactly kind, id, revision and digest",
        )
    if not all(isinstance(subject[name], str) and subject[name].strip() for name in ("kind", "id", "digest")):
        raise ProvenanceError("provenance.subject", "subject kind, id and digest must be non-empty strings")
    if not isinstance(subject["revision"], int) or subject["revision"] < 1:
        raise ProvenanceError("provenance.subject", "subject revision must be a positive integer")
    return {
        "kind": subject["kind"].strip(),
        "id": subject["id"].strip(),
        "revision": subject["revision"],
        "digest": subject["digest"].strip(),
    }


def parse(record: dict) -> Provenance:
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ProvenanceError("provenance.schema", f"expected schema {SCHEMA}")
    unknown = sorted(set(record) - TOP)
    if unknown:
        raise ProvenanceError("provenance.unknown_field", f"unknown fields: {', '.join(unknown)}")
    _scan({k: v for k, v in record.items() if k != "schema"}, "")
    actor = record.get("actor")
    if not isinstance(actor, str) or not actor.strip():
        raise ProvenanceError("provenance.actor", "'actor' must be a non-empty string")
    fallback = record.get("fallback") or {}
    if set(fallback) - {"used", "from", "reason"}:
        raise ProvenanceError("provenance.unknown_field", "unknown fallback fields")
    used = bool(fallback.get("used", False))
    origin = fallback.get("from")
    if used:
        if not isinstance(origin, dict) or not origin.get("provider") or not origin.get("model"):
            raise ProvenanceError("provenance.fallback", "fallback.from must name the original provider and model")
        if not str(fallback.get("reason") or "").strip():
            raise ProvenanceError("provenance.fallback", "fallback.reason is required when a fallback was used")
    return Provenance(
        actor=actor.strip(), subject=_subject(record), fallback_used=used,
        fallback_from={k: str(v) for k, v in origin.items()} if used else None,
        fallback_reason=str(fallback["reason"]).strip() if used else None,
        **{name: _value(record, name) for name in FIELDS},
    )  # fmt: skip


def normalize(text: str) -> str:
    return text.strip().casefold()


def compare(a: Provenance, b: Provenance, dimension: str, min_source: str = "declared") -> str:
    """Return 'same', 'distinct' or 'unknown'. Unknown is never distinct."""
    if dimension not in DIMENSIONS:
        raise ProvenanceError("provenance.dimension", f"unknown dimension {dimension!r}")
    if min_source not in ("observed", "declared"):
        raise ProvenanceError("provenance.source", "min_source must be observed or declared")
    if dimension == "actor":
        return "same" if normalize(a.actor) == normalize(b.actor) else "distinct"
    left, right = getattr(a, dimension), getattr(b, dimension)
    if any(v.value is None or RANK[v.source] < RANK[min_source] for v in (left, right)):
        return "unknown"
    return "same" if normalize(left.value) == normalize(right.value) else "distinct"


def evaluate_separation(
    required: list[str], producer: Provenance, reviewer: Provenance, min_source: str = "declared"
) -> dict:
    """Deterministic decision: every required dimension must be 'distinct'."""
    blockers = []
    for dimension in sorted(set(required), key=DIMENSIONS.index):
        status = compare(producer, reviewer, dimension, min_source)
        if status == "distinct":
            continue
        if status == "same":
            message = f"reviewer and producer share the same {dimension}; use a different {dimension}"
        else:
            message = (
                f"{dimension} is unknown for the producer or reviewer at trust level {min_source}; "
                f"declare or observe it, unknown is not distinct"
            )
        blockers.append({"dimension": dimension, "status": status, "message": message})
    return {"allowed": not blockers, "blockers": blockers}
