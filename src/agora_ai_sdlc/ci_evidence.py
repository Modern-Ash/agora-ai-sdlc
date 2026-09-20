"""Provider-neutral CI/CD evidence normalization and gate bundles."""

import hashlib
import json
import re
from collections.abc import Iterable
from urllib.parse import urlparse

import yaml
from agora.model import AddEvidenceInput

from agora_ai_sdlc.depth_profiles import asset_root

SCHEMA = "agora-ai-sdlc/ci-evidence/v1"
PROFILE_SCHEMA = "agora-ai-sdlc/integration-profile/v1"
FIELDS = {
    "schema",
    "provider",
    "repository",
    "commit",
    "environment",
    "run_id",
    "category",
    "status",
    "evidence_refs",
}
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class CIEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def load_profile() -> dict:
    path = asset_root("profiles") / "integrations" / "ci" / "profile.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA or data.get("id") != "generic-ci-evidence":
        raise CIEvidenceError("ci.profile.invalid", "invalid generic CI evidence profile")
    return data


def _identity(value: object, field: str, limit: int) -> str:
    text = str(value) if value is not None else ""
    if not text or len(text) > limit or not IDENTITY.fullmatch(text):
        raise CIEvidenceError("ci.fact.identity", f"invalid {field}")
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
        raise CIEvidenceError("ci.fact.reference", f"unsafe or invalid {field}")
    return text


def _commit(value: object) -> str:
    commit = str(value).casefold()
    if not COMMIT.fullmatch(commit):
        raise CIEvidenceError("ci.fact.commit", "commit must be a full 40 or 64 character hexadecimal id")
    return commit


def normalize_evidence(
    payload: dict,
    *,
    expected_repository: str,
    expected_commit: str,
    expected_environment: str,
) -> dict:
    """Normalize one bounded observation and assess its freshness."""
    if not isinstance(payload, dict):
        raise CIEvidenceError("ci.fact.type", "CI evidence must be an object")
    missing = sorted(FIELDS - set(payload))
    unknown = sorted(set(payload) - FIELDS)
    if missing or unknown:
        raise CIEvidenceError("ci.fact.fields", f"missing={missing}, unknown={unknown}")
    if payload["schema"] != SCHEMA:
        raise CIEvidenceError("ci.fact.schema", f"expected {SCHEMA}")
    profile = load_profile()
    identity_limit = int(profile["limits"]["max_identity_length"])
    reference_limit = int(profile["limits"]["max_reference_length"])
    provider = _identity(payload["provider"], "provider", identity_limit)
    run_id = _identity(payload["run_id"], "run_id", identity_limit)
    environment = _identity(payload["environment"], "environment", identity_limit)
    repository = _url(payload["repository"], "repository", reference_limit).rstrip("/")
    commit = _commit(payload["commit"])
    expected_repository = _url(expected_repository, "expected repository", reference_limit).rstrip("/")
    expected_commit = _commit(expected_commit)
    expected_environment = _identity(expected_environment, "expected environment", identity_limit)
    category = str(payload["category"])
    status = str(payload["status"])
    if category not in profile["categories"]:
        raise CIEvidenceError("ci.fact.category", f"unsupported category {category!r}")
    if status not in profile["statuses"]:
        raise CIEvidenceError("ci.fact.status", f"unsupported status {status!r}")
    references = payload["evidence_refs"]
    if not isinstance(references, list) or not references or len(references) > profile["limits"]["max_references"]:
        raise CIEvidenceError("ci.fact.references", "evidence_refs must be a non-empty bounded array")
    evidence_refs = tuple(_url(value, "evidence reference", reference_limit) for value in references)
    if len(set(evidence_refs)) != len(evidence_refs):
        raise CIEvidenceError("ci.fact.references", "evidence_refs must not contain duplicates")

    blockers = []
    if repository != expected_repository:
        blockers.append({"code": "ci.repository.mismatch", "message": "result belongs to another repository"})
    if commit != expected_commit:
        blockers.append({"code": "ci.commit.stale", "message": "result does not target the expected commit"})
    if environment != expected_environment:
        blockers.append({"code": "ci.environment.mismatch", "message": "result belongs to another environment"})
    if status != "success":
        blockers.append({"code": f"ci.status.{status}", "message": f"result status is {status}"})

    identity = {"provider": provider, "repository": repository, "run_id": run_id, "category": category}
    dedupe_payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    fact = {
        "schema": SCHEMA,
        **identity,
        "commit": commit,
        "environment": environment,
        "status": status,
        "evidence_refs": evidence_refs,
        "allowed": not blockers,
        "blockers": blockers,
        "dedupe_key": f"sha256:{hashlib.sha256(dedupe_payload).hexdigest()}",
    }
    fingerprint_payload = json.dumps(fact, sort_keys=True, separators=(",", ":")).encode()
    fact["fingerprint"] = f"sha256:{hashlib.sha256(fingerprint_payload).hexdigest()}"
    return fact


def ingest_evidence(existing: Iterable[dict], candidate: dict) -> tuple[tuple[dict, ...], bool]:
    """Append an immutable run/category observation once; reject changed duplicates."""
    observations = tuple(existing)
    for item in observations:
        if item.get("dedupe_key") != candidate.get("dedupe_key"):
            continue
        if item.get("fingerprint") == candidate.get("fingerprint"):
            return observations, False
        raise CIEvidenceError("ci.run.conflict", "run/category identity was reused with different evidence")
    return (*observations, candidate), True


def evaluate_bundle(
    evidence_type: str,
    facts: Iterable[dict],
    *,
    expected_repository: str,
    expected_commit: str,
    expected_environment: str,
) -> dict:
    """Resolve one Core gate evidence type from its required neutral categories."""
    profile = load_profile()
    if evidence_type not in profile["bundles"]:
        raise CIEvidenceError("ci.bundle.unknown", f"unknown evidence bundle {evidence_type!r}")
    identity_limit = int(profile["limits"]["max_identity_length"])
    reference_limit = int(profile["limits"]["max_reference_length"])
    expected_repository = _url(expected_repository, "expected repository", reference_limit).rstrip("/")
    expected_commit = _commit(expected_commit)
    expected_environment = _identity(expected_environment, "expected environment", identity_limit)
    facts = tuple(facts)
    selected = []
    blockers = []
    for category in profile["bundles"][evidence_type]:
        candidates = [fact for fact in facts if fact.get("category") == category]
        current = next(
            (
                fact
                for fact in candidates
                if fact.get("allowed") is True
                and fact.get("repository") == expected_repository
                and fact.get("commit") == expected_commit
                and fact.get("environment") == expected_environment
                and fact.get("status") == "success"
            ),
            None,
        )
        if current is None:
            blockers.append(
                {
                    "code": "ci.bundle.missing",
                    "message": f"no successful current {category} evidence",
                }
            )
        else:
            selected.append(current)
    references = tuple(dict.fromkeys(ref for fact in selected for ref in fact["evidence_refs"]))
    if len(references) > profile["limits"]["max_references"]:
        blockers.append({"code": "ci.bundle.references", "message": "bundle has too many evidence references"})
    fingerprints = tuple(fact["fingerprint"] for fact in selected)
    bundle_payload = json.dumps(
        {
            "evidence_type": evidence_type,
            "repository": expected_repository,
            "commit": expected_commit,
            "environment": expected_environment,
            "fingerprints": fingerprints,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "evidence_type": evidence_type,
        "allowed": not blockers,
        "repository": expected_repository,
        "commit": expected_commit,
        "environment": expected_environment,
        "categories": tuple(profile["bundles"][evidence_type]),
        "evidence_refs": references,
        "blockers": blockers,
        "dedupe_key": f"sha256:{hashlib.sha256(bundle_payload).hexdigest()}",
    }


def core_evidence_input(
    bundle: dict,
    *,
    swarm_id: str,
    work_id: str,
    actor_id: str,
) -> AddEvidenceInput:
    """Map a bundle to Core; a blocked bundle is always recorded as failure."""
    return AddEvidenceInput(
        swarm_id=swarm_id,
        work_id=work_id,
        actor_id=actor_id,
        type=bundle["evidence_type"],
        result="success" if bundle["allowed"] else "failure",
        artifact_refs=list(bundle["evidence_refs"]),
        evidence_id=f"ci-{bundle['evidence_type']}-{bundle['dedupe_key'][7:19]}",
        tested_commit=bundle["commit"],
        environment=bundle["environment"],
        dedupe_key=bundle["dedupe_key"],
    )
