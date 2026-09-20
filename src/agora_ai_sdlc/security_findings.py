"""Provider-neutral security findings, decisions, and depth thresholds."""

import hashlib
import json
import re
from collections.abc import Iterable
from urllib.parse import urlparse

import yaml
from agora.model import AddEvidenceInput, AddReviewFindingInput, DecideReviewFindingInput

from agora_ai_sdlc.depth_profiles import asset_root

SCHEMA = "agora-ai-sdlc/security-finding/v1"
PROFILE_SCHEMA = "agora-ai-sdlc/integration-profile/v1"
FINDING_FIELDS = {
    "schema",
    "id",
    "category",
    "severity",
    "rule",
    "summary",
    "location",
    "scanner",
    "scanner_finding_id",
    "report_ref",
}
DECISION_FIELDS = {"kind", "actor", "actor_kind", "role", "reason", "evidence_ref"}
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class SecurityFindingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def load_profile() -> dict:
    path = asset_root("profiles") / "integrations" / "security" / "profile.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA or data.get("id") != "security-findings":
        raise SecurityFindingError("security.profile.invalid", "invalid security findings profile")
    return data


def _text(value: object, field: str, limit: int, *, slug: bool = False) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or len(text) > limit or (slug and not SLUG.fullmatch(text)):
        raise SecurityFindingError("security.finding.field", f"invalid {field}")
    return text


def _url(value: object, field: str, limit: int) -> str:
    text = str(value) if value is not None else ""
    parsed = urlparse(text)
    if (
        not text
        or len(text) > limit
        or parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise SecurityFindingError("security.finding.reference", f"unsafe or invalid {field}")
    return text


def _original_view(finding: dict) -> dict:
    return {key: finding[key] for key in sorted(FINDING_FIELDS - {"schema"})}


def _fingerprint(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def normalize_finding(payload: dict) -> dict:
    """Normalize one redacted scanner finding as an immutable open record."""
    if not isinstance(payload, dict):
        raise SecurityFindingError("security.finding.type", "security finding must be an object")
    missing = sorted(FINDING_FIELDS - set(payload))
    unknown = sorted(set(payload) - FINDING_FIELDS)
    if missing or unknown:
        raise SecurityFindingError("security.finding.fields", f"missing={missing}, unknown={unknown}")
    if payload["schema"] != SCHEMA:
        raise SecurityFindingError("security.finding.schema", f"expected {SCHEMA}")
    profile = load_profile()
    limit = int(profile["limits"]["max_text_length"])
    reference_limit = int(profile["limits"]["max_reference_length"])
    category = str(payload["category"])
    severity = str(payload["severity"])
    if category not in profile["categories"]:
        raise SecurityFindingError("security.finding.category", f"unsupported category {category!r}")
    if severity not in profile["severities"]:
        raise SecurityFindingError("security.finding.severity", f"unsupported severity {severity!r}")
    location = None if payload["location"] is None else _text(payload["location"], "location", limit)
    finding = {
        "schema": SCHEMA,
        "id": _text(payload["id"], "id", limit, slug=True),
        "category": category,
        "severity": severity,
        "rule": _text(payload["rule"], "rule", limit),
        "summary": _text(payload["summary"], "summary", limit),
        "location": location,
        "scanner": _text(payload["scanner"], "scanner", limit),
        "scanner_finding_id": _text(payload["scanner_finding_id"], "scanner_finding_id", limit),
        "report_ref": _url(payload["report_ref"], "report_ref", reference_limit),
        "status": "open",
        "decision": None,
    }
    finding["original_fingerprint"] = _fingerprint(_original_view(finding))
    finding["fingerprint"] = _fingerprint({key: finding[key] for key in finding if key != "fingerprint"})
    return finding


def _validate_decision(decision: dict) -> dict:
    if not isinstance(decision, dict):
        raise SecurityFindingError("security.decision.type", "decision must be an object")
    missing = sorted(DECISION_FIELDS - set(decision))
    unknown = sorted(set(decision) - DECISION_FIELDS)
    if missing or unknown:
        raise SecurityFindingError("security.decision.fields", f"missing={missing}, unknown={unknown}")
    profile = load_profile()
    kind = str(decision["kind"])
    if kind not in profile["decisions"]:
        raise SecurityFindingError("security.decision.kind", f"unsupported decision {kind!r}")
    limit = int(profile["limits"]["max_text_length"])
    policy = profile["decisions"][kind]
    normalized = {
        "kind": kind,
        "actor": _text(decision["actor"], "decision.actor", limit),
        "actor_kind": _text(decision["actor_kind"], "decision.actor_kind", limit),
        "role": _text(decision["role"], "decision.role", limit),
        "reason": _text(decision["reason"], "decision.reason", limit),
        "evidence_ref": _url(
            decision["evidence_ref"],
            "decision.evidence_ref",
            int(profile["limits"]["max_reference_length"]),
        ),
    }
    if normalized["role"] not in policy["roles"]:
        raise SecurityFindingError("security.decision.role", f"{normalized['role']} cannot authorize {kind}")
    if normalized["actor_kind"] not in policy.get("actor_kinds", ["human", "ai-agent"]):
        raise SecurityFindingError("security.decision.actor_kind", f"{kind} requires an authorized human actor")
    return normalized


def decide_finding(finding: dict, decision: dict) -> dict:
    """Add an accountable decision without changing the original finding fields."""
    _validate_record(finding)
    if finding["status"] != "open":
        raise SecurityFindingError("security.decision.closed", f"finding {finding['id']} is already decided")
    normalized = _validate_decision(decision)
    decided = dict(finding)
    decided["status"] = normalized["kind"]
    decided["decision"] = normalized
    decided["fingerprint"] = _fingerprint({key: decided[key] for key in decided if key != "fingerprint"})
    return decided


def _validate_record(finding: dict) -> None:
    required = FINDING_FIELDS | {"status", "decision", "original_fingerprint", "fingerprint"}
    if not isinstance(finding, dict) or set(finding) != required:
        raise SecurityFindingError("security.finding.record", "invalid normalized finding record")
    normalized = normalize_finding({key: finding[key] for key in FINDING_FIELDS})
    if finding["original_fingerprint"] != normalized["original_fingerprint"]:
        raise SecurityFindingError("security.finding.mutated", "original finding fields changed after normalization")
    expected = _fingerprint({key: finding[key] for key in finding if key != "fingerprint"})
    if finding["fingerprint"] != expected:
        raise SecurityFindingError("security.finding.fingerprint", "finding fingerprint does not match its content")
    profile = load_profile()
    if finding["status"] not in profile["statuses"]:
        raise SecurityFindingError("security.finding.status", f"unsupported status {finding['status']!r}")
    if finding["status"] == "open":
        if finding["decision"] is not None:
            raise SecurityFindingError("security.finding.decision", "open finding cannot have a decision")
    else:
        decision = _validate_decision(finding["decision"])
        if decision["kind"] != finding["status"]:
            raise SecurityFindingError("security.finding.decision", "decision kind does not match finding status")


def evaluate_findings(depth: str, findings: Iterable[dict], *, scan_refs: Iterable[str]) -> dict:
    """Apply the active depth threshold and return security-scan eligibility."""
    profile = load_profile()
    if depth not in profile["thresholds"]:
        raise SecurityFindingError("security.depth.unknown", f"unknown depth profile {depth!r}")
    findings = tuple(findings)
    if len(findings) > profile["limits"]["max_findings"]:
        raise SecurityFindingError("security.findings.limit", "too many findings in one assessment")
    for finding in findings:
        _validate_record(finding)
    ids = [finding["id"] for finding in findings]
    if len(set(ids)) != len(ids):
        raise SecurityFindingError("security.findings.duplicate", "finding ids must be unique")
    findings = tuple(sorted(findings, key=lambda finding: finding["id"]))
    references = tuple(
        dict.fromkeys(
            [
                *(_url(value, "scan reference", int(profile["limits"]["max_reference_length"])) for value in scan_refs),
                *(finding.get("report_ref") for finding in findings),
                *(
                    finding["decision"]["evidence_ref"]
                    for finding in findings
                    if isinstance(finding.get("decision"), dict)
                ),
            ]
        )
    )
    if not references or len(references) > profile["limits"]["max_references"]:
        raise SecurityFindingError("security.references.limit", "assessment references must be non-empty and bounded")
    threshold = profile["thresholds"][depth]
    blockers = []
    for finding in findings:
        if finding["status"] != "open":
            continue
        if finding["severity"] == "unknown":
            blockers.append(
                {"code": "security.severity.unknown", "finding": finding["id"], "message": "unknown severity"}
            )
        elif profile["severity_rank"][finding["severity"]] >= profile["severity_rank"][threshold]:
            blockers.append(
                {
                    "code": "security.finding.open",
                    "finding": finding["id"],
                    "message": f"open {finding['severity']} finding meets {depth} threshold {threshold}",
                }
            )
    digest = _fingerprint(
        {
            "depth": depth,
            "findings": [finding["fingerprint"] for finding in findings],
            "references": references,
        }
    )
    return {
        "allowed": not blockers,
        "depth": depth,
        "threshold": threshold,
        "findings": len(findings),
        "references": references,
        "blockers": blockers,
        "dedupe_key": digest,
    }


def to_core_finding_input(finding: dict, *, swarm_id: str, work_id: str) -> AddReviewFindingInput:
    _validate_record(finding)
    return AddReviewFindingInput(
        id=finding["id"],
        swarm_id=swarm_id,
        work_id=work_id,
        pass_id=f"security-{finding['category']}",
        severity="critical" if finding["severity"] == "unknown" else finding["severity"],
        policy=finding["rule"],
        summary=finding["summary"],
        location=finding["location"],
    )


def to_core_decision_input(finding: dict) -> DecideReviewFindingInput:
    _validate_record(finding)
    if finding["status"] == "open":
        raise SecurityFindingError("security.decision.missing", "open finding has no Core decision")
    profile = load_profile()
    decision = finding["decision"]
    return DecideReviewFindingInput(
        id=finding["id"],
        decision=profile["decisions"][decision["kind"]]["core_status"],
        actor=decision["actor"],
        reason=decision["reason"],
    )


def security_evidence_input(
    assessment: dict,
    *,
    swarm_id: str,
    work_id: str,
    actor_id: str,
    tested_commit: str,
    environment: str,
) -> AddEvidenceInput:
    commit = tested_commit.casefold()
    if not COMMIT.fullmatch(commit):
        raise SecurityFindingError("security.evidence.commit", "tested_commit must be a full commit id")
    return AddEvidenceInput(
        swarm_id=swarm_id,
        work_id=work_id,
        actor_id=actor_id,
        type="security-scan",
        result="success" if assessment["allowed"] else "failure",
        artifact_refs=list(assessment["references"]),
        evidence_id=f"security-scan-{assessment['dedupe_key'][7:19]}",
        tested_commit=commit,
        environment=_text(environment, "environment", 128, slug=True),
        dedupe_key=assessment["dedupe_key"],
    )
