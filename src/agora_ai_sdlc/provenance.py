"""Runtime, provider and model provenance: validation and deterministic separation comparison.

Every value is `observed` (measured by the platform), `declared` (asserted by a configuration or an actor) or
`unavailable`. Unknown provenance never counts as distinct. Credentials and endpoints are never accepted.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

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
    fallback_used: bool | None
    fallback_source: str
    fallback_from: dict[str, str] | None
    fallback_reason: str | None
    subject: dict | None


class CoreSession(Protocol):
    id: str
    actor: str
    executor: str | None
    integration: str
    provider: str
    model: str


class CoreUsage(Protocol):
    session_id: str | None


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
    fallback = record.get("fallback")
    used, fallback_source, origin, fallback_reason = _fallback(fallback)
    return Provenance(
        actor=actor.strip(), subject=_subject(record), fallback_used=used, fallback_source=fallback_source,
        fallback_from=origin, fallback_reason=fallback_reason,
        **{name: _value(record, name) for name in FIELDS},
    )  # fmt: skip


def _fallback(raw: object) -> tuple[bool | None, str, dict[str, str] | None, str | None]:
    if raw is None:
        return None, "unavailable", None, None
    if not isinstance(raw, dict) or set(raw) - {"source", "used", "from", "reason"}:
        raise ProvenanceError("provenance.fallback", "fallback must contain source and fallback metadata")
    source = raw.get("source")
    if source not in SOURCES:
        raise ProvenanceError("provenance.source", f"fallback source {source!r} must be one of {', '.join(SOURCES)}")
    if source == "unavailable":
        if set(raw) != {"source"}:
            raise ProvenanceError("provenance.unavailable_value", "unavailable fallback must not carry metadata")
        return None, source, None, None
    used = raw.get("used")
    if not isinstance(used, bool):
        raise ProvenanceError("provenance.fallback", "fallback.used must be boolean when declared or observed")
    origin = raw.get("from")
    reason = raw.get("reason")
    if not used:
        if origin is not None or reason is not None:
            raise ProvenanceError("provenance.fallback", "unused fallback must not carry from or reason")
        return False, source, None, None
    if not isinstance(origin, dict) or set(origin) != {"runtime", "provider", "model"}:
        raise ProvenanceError("provenance.fallback", "fallback.from must name runtime, provider and model")
    if not all(isinstance(value, str) and value.strip() for value in origin.values()):
        raise ProvenanceError("provenance.fallback", "fallback.from values must be non-empty strings")
    if not isinstance(reason, str) or not reason.strip():
        raise ProvenanceError("provenance.fallback", "fallback.reason is required when a fallback was used")
    return True, source, {key: value.strip() for key, value in origin.items()}, reason.strip()


def from_core_session(session: CoreSession, *, subject: dict | None = None) -> Provenance:
    """Map fields Core 0.8 persists; unsupported provenance remains unavailable."""
    executor = session.executor or session.actor
    record = {
        "schema": SCHEMA,
        "actor": executor,
        "runtime": {"value": session.integration, "source": "declared"},
        "runtime_version": {"source": "unavailable"},
        "provider": {"value": session.provider, "source": "declared"},
        "model": {"value": session.model, "source": "declared"},
        "selection_reason": {"source": "unavailable"},
        "fallback": {"source": "unavailable"},
    }
    if subject is not None:
        record["subject"] = subject
    return parse(record)


def from_core_usage(
    usage: CoreUsage,
    sessions: Mapping[str, CoreSession],
    *,
    subject: dict | None = None,
) -> Provenance:
    """Resolve usage provenance through Core's authoritative session link."""
    if not usage.session_id:
        raise ProvenanceError("provenance.core_usage", "Core usage record has no session reference")
    session = sessions.get(usage.session_id)
    if session is None:
        raise ProvenanceError("provenance.core_usage", f"Core session {usage.session_id!r} is unavailable")
    return from_core_session(session, subject=subject)


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
