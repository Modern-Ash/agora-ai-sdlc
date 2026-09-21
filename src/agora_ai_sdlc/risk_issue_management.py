"""Provider-neutral risk and issue management records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA = "agora-ai-sdlc/risk-issue-record/v1"
TYPES = {"risk", "issue"}
SEVERITIES = {"low", "medium", "high", "critical"}
STATUSES = {"open", "mitigated", "resolved", "closed"}
PROBABILITIES = {"low", "medium", "high"}
IMPACTS = {"low", "medium", "high", "critical"}
ID_PATTERN = re.compile(r"^(RSK|ISS)-[0-9]{3,}$")
REFERENCE = re.compile(r"^[a-z][a-z0-9+.-]*:[^\s]+$")
SECRET_MARKERS = ("token=", "password=", "secret=", "api_key=", "apikey=", "authorization=")


class RiskIssueError(ValueError):
    """Stable validation error for risk/issue records."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class RiskIssueRecord:
    id: str
    type: str
    title: str
    owner: str
    severity: str
    status: str
    revision: int
    scope: tuple[str, ...]
    evidence: tuple[str, ...]
    probability: str | None
    impact: str
    mitigation: str | None
    next_action: str | None

    @property
    def blocking(self) -> bool:
        return self.status == "open" and self.severity in {"high", "critical"}


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RiskIssueError("risk-issue.type", f"{field!r} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _string(value, field)


def _strings(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise RiskIssueError("risk-issue.type", f"{field!r} must be a list of non-empty strings")
    normalized = tuple(item.strip() for item in value)
    if not allow_empty and not normalized:
        raise RiskIssueError("risk-issue.type", f"{field!r} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise RiskIssueError("risk-issue.duplicate", f"{field!r} contains duplicates")
    return normalized


def _validate_reference(reference: str) -> None:
    lowered = reference.casefold()
    if REFERENCE.fullmatch(reference) is None:
        raise RiskIssueError("risk-issue.evidence", "evidence must use opaque logical references")
    if reference.startswith(("http:", "https:")):
        raise RiskIssueError("risk-issue.endpoint", "raw network endpoints are not allowed")
    if any(marker in lowered for marker in SECRET_MARKERS):
        raise RiskIssueError("risk-issue.secret", "evidence reference contains forbidden credential material")


def parse_record(contents: str) -> RiskIssueRecord:
    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as error:
        raise RiskIssueError("risk-issue.syntax", "record is not valid YAML") from error
    if not isinstance(data, dict):
        raise RiskIssueError("risk-issue.syntax", "record must be a mapping")
    expected = {
        "schema",
        "id",
        "type",
        "title",
        "owner",
        "severity",
        "status",
        "revision",
        "scope",
        "evidence",
        "probability",
        "impact",
        "mitigation",
        "next_action",
    }
    if set(data) != expected:
        raise RiskIssueError("risk-issue.fields", "record fields do not match v1 contract")
    if data.get("schema") != SCHEMA:
        raise RiskIssueError("risk-issue.schema", f"unsupported schema {data.get('schema')!r}")

    record_id = _string(data["id"], "id")
    if ID_PATTERN.fullmatch(record_id) is None:
        raise RiskIssueError("risk-issue.id", "id must use RSK-NNN or ISS-NNN")
    record_type = _string(data["type"], "type")
    if record_type not in TYPES:
        raise RiskIssueError("risk-issue.kind", f"unsupported type {record_type!r}")
    if record_type == "risk" and not record_id.startswith("RSK-"):
        raise RiskIssueError("risk-issue.id_kind", "risk ids must use RSK- prefix")
    if record_type == "issue" and not record_id.startswith("ISS-"):
        raise RiskIssueError("risk-issue.id_kind", "issue ids must use ISS- prefix")

    severity = _string(data["severity"], "severity")
    if severity not in SEVERITIES:
        raise RiskIssueError("risk-issue.severity", f"unsupported severity {severity!r}")
    status = _string(data["status"], "status")
    if status not in STATUSES:
        raise RiskIssueError("risk-issue.status", f"unsupported status {status!r}")
    revision = data["revision"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise RiskIssueError("risk-issue.revision", "revision must be a positive integer")

    scope = _strings(data["scope"], "scope")
    evidence = _strings(data["evidence"], "evidence", allow_empty=True)
    for reference in evidence:
        _validate_reference(reference)

    probability = _optional_string(data["probability"], "probability")
    impact = _string(data["impact"], "impact")
    if impact not in IMPACTS:
        raise RiskIssueError("risk-issue.impact", f"unsupported impact {impact!r}")
    mitigation = _optional_string(data["mitigation"], "mitigation")
    next_action = _optional_string(data["next_action"], "next_action")

    if record_type == "risk":
        if probability not in PROBABILITIES:
            raise RiskIssueError("risk-issue.probability", "risk probability must be low, medium or high")
        if mitigation is None:
            raise RiskIssueError("risk-issue.mitigation", "risk mitigation is required")
        if next_action is not None:
            raise RiskIssueError("risk-issue.next_action", "risk records do not use next_action")
    else:
        if probability is not None:
            raise RiskIssueError("risk-issue.probability", "issue probability must be null")
        if next_action is None:
            raise RiskIssueError("risk-issue.next_action", "issue next_action is required")
        if mitigation is not None:
            raise RiskIssueError("risk-issue.mitigation", "issue records do not use mitigation")

    if status in {"resolved", "closed"} and not evidence:
        raise RiskIssueError("risk-issue.closure_evidence", "resolved/closed records require evidence")

    return RiskIssueRecord(
        record_id,
        record_type,
        _string(data["title"], "title"),
        _string(data["owner"], "owner"),
        severity,
        status,
        revision,
        scope,
        evidence,
        probability,
        impact,
        mitigation,
        next_action,
    )


def load_record(path: Path) -> RiskIssueRecord:
    if not path.is_file():
        raise RiskIssueError("risk-issue.file", f"record not found: {path}")
    return parse_record(path.read_text(encoding="utf-8"))


def portfolio(records: tuple[RiskIssueRecord, ...]) -> dict:
    by_id: dict[str, RiskIssueRecord] = {}
    for record in records:
        if record.id in by_id:
            raise RiskIssueError("risk-issue.duplicate_id", f"duplicate record {record.id!r}")
        by_id[record.id] = record
    ordered = tuple(sorted(records, key=lambda item: item.id))
    open_records = tuple(item for item in ordered if item.status in {"open", "mitigated"})
    blocking = tuple(item for item in ordered if item.blocking)
    return {
        "schema": "agora-ai-sdlc/risk-issue-portfolio/v1",
        "total": len(ordered),
        "open": len(open_records),
        "blocking": len(blocking),
        "by_type": {
            "risk": sum(item.type == "risk" for item in ordered),
            "issue": sum(item.type == "issue" for item in ordered),
        },
        "blocking_ids": [item.id for item in blocking],
        "records": [
            {
                "id": item.id,
                "type": item.type,
                "severity": item.severity,
                "status": item.status,
                "owner": item.owner,
            }
            for item in ordered
        ],
    }
