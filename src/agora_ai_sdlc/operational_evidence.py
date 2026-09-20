"""Provider-neutral operational observations and Agora Core control-band mapping."""

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

import yaml
from agora.model import AddControlBandInput, AddEvidenceInput, EvaluateControlBandInput

from agora_ai_sdlc.depth_profiles import asset_root

PROFILE_SCHEMA = "agora-ai-sdlc/integration-profile/v1"
METRIC_SCHEMA = "agora-ai-sdlc/metric-observation/v1"
RELEASE_SCHEMA = "agora-ai-sdlc/release-observation/v1"
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
REVISION = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
WINDOW = re.compile(r"^[1-9][0-9]*[smh]$")
PROVIDERS = {"cloudwatch", "azure-monitor", "gcp-monitoring", "prometheus", "opentelemetry"}


class OperationalEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def load_profile() -> dict:
    path = asset_root("profiles") / "integrations" / "observability" / "profile.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("schema") != PROFILE_SCHEMA
        or data.get("id") != "operational-evidence"
        or data.get("provider") != "neutral"
    ):
        raise OperationalEvidenceError("observability.profile.invalid", "invalid operational evidence profile")
    return data


def _identity(value: object, field: str) -> str:
    text = str(value) if value is not None else ""
    limit = int(load_profile()["limits"]["max_identity_length"])
    if not text or len(text) > limit or not IDENTITY.fullmatch(text):
        raise OperationalEvidenceError("observability.fact.identity", f"invalid {field}")
    return text


def _source(value: object) -> str:
    text = str(value) if value is not None else ""
    parsed = urlparse(text)
    limit = int(load_profile()["limits"]["max_reference_length"])
    if (
        not text
        or len(text) > limit
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise OperationalEvidenceError("observability.fact.source", "source must be a bounded HTTPS reference")
    return text


def _time(value: object, field: str) -> datetime:
    text = str(value) if value is not None else ""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise OperationalEvidenceError("observability.fact.timestamp", f"invalid {field}") from error
    if parsed.tzinfo is None:
        raise OperationalEvidenceError("observability.fact.timestamp", f"{field} must include a timezone")
    return parsed.astimezone(UTC)


def _timestamp(value: object, field: str = "timestamp") -> str:
    return _time(value, field).isoformat().replace("+00:00", "Z")


def _unix_timestamp(value: object, divisor: int = 1) -> str:
    try:
        seconds = float(value) / divisor
        parsed = datetime.fromtimestamp(seconds, tz=UTC)
    except (TypeError, ValueError, OverflowError) as error:
        raise OperationalEvidenceError("observability.fact.timestamp", "invalid Unix timestamp") from error
    return parsed.isoformat().replace("+00:00", "Z")


def _duration(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds <= 0 or not seconds.is_integer():
        raise OperationalEvidenceError("observability.fact.window", "window must be a positive whole duration")
    whole = int(seconds)
    if whole % 3600 == 0:
        return f"{whole // 3600}h"
    if whole % 60 == 0:
        return f"{whole // 60}m"
    return f"{whole}s"


def _interval(start: object, end: object) -> tuple[str, str]:
    start_time = _time(start, "window start")
    end_time = _time(end, "timestamp")
    return _duration((end_time - start_time).total_seconds()), end_time.isoformat().replace("+00:00", "Z")


def _provider_fields(provider: str, payload: dict) -> dict:
    try:
        if provider == "cloudwatch":
            return {
                "name": {"HTTPErrorRate": "http.error_rate"}[payload["MetricName"]],
                "value": payload["Average"],
                "unit": payload["Unit"],
                "window": _duration(float(payload["Period"])),
                "environment": payload["Environment"],
                "source": payload["DashboardUrl"],
                "timestamp": payload["Timestamp"],
            }
        if provider == "azure-monitor":
            grain = {"PT5M": "5m"}.get(payload["timeGrain"])
            return {**payload, "window": grain, "source": payload["portalUrl"], "value": payload["average"]}
        if provider == "gcp-monitoring":
            window, timestamp = _interval(
                payload["point"]["interval"]["startTime"], payload["point"]["interval"]["endTime"]
            )
            return {
                "name": {"custom.googleapis.com/http/error_rate": "http.error_rate"}[payload["metric"]["type"]],
                "value": payload["point"]["value"]["doubleValue"],
                "unit": payload["unit"],
                "window": window,
                "environment": payload["environment"],
                "source": payload["source"],
                "timestamp": timestamp,
            }
        if provider == "prometheus":
            return {
                "name": {"http_error_rate": "http.error_rate"}[payload["metric"]["__name__"]],
                "value": payload["value"][1],
                "unit": payload["unit"],
                "window": payload["window"],
                "environment": payload["metric"]["environment"],
                "source": payload["source"],
                "timestamp": _unix_timestamp(payload["value"][0]),
            }
        window, timestamp = _interval(
            _unix_timestamp(payload["start_time_unix_nano"], 1_000_000_000),
            _unix_timestamp(payload["time_unix_nano"], 1_000_000_000),
        )
        return {
            "name": payload["name"],
            "value": payload["value"],
            "unit": payload["unit"],
            "window": window,
            "environment": payload["attributes"]["deployment.environment.name"],
            "source": payload["source"],
            "timestamp": timestamp,
        }
    except (KeyError, TypeError, IndexError, ValueError) as error:
        raise OperationalEvidenceError("observability.fact.mapping", f"malformed {provider} metric payload") from error


def normalize_metric(
    provider: str,
    payload: dict,
    *,
    expected_environment: str,
    observed_at: str,
) -> dict:
    """Translate one provider fixture and assess environment and freshness."""
    if provider not in PROVIDERS or not isinstance(payload, dict):
        raise OperationalEvidenceError("observability.provider.unsupported", f"unsupported provider {provider!r}")
    fields = _provider_fields(provider, payload)
    profile = load_profile()
    name = _identity(fields.get("name"), "metric name")
    environment = _identity(fields.get("environment"), "environment")
    expected_environment = _identity(expected_environment, "expected environment")
    unit = str(fields.get("unit") or "").strip().casefold()
    unit = {"%": "percent", "percent": "percent"}.get(unit, unit)
    window = str(fields.get("window") or "").strip().casefold()
    if not unit:
        raise OperationalEvidenceError("observability.fact.unit", "metric unit is required")
    if not WINDOW.fullmatch(window):
        raise OperationalEvidenceError("observability.fact.window", "metric window is required and must be bounded")
    try:
        value = float(fields.get("value"))
    except (TypeError, ValueError) as error:
        raise OperationalEvidenceError("observability.fact.value", "metric value must be numeric") from error
    if not math.isfinite(value):
        raise OperationalEvidenceError("observability.fact.value", "metric value must be finite")
    timestamp = _timestamp(fields.get("timestamp"))
    capture = _time(observed_at, "observed_at")
    age = (capture - _time(timestamp, "timestamp")).total_seconds()
    blockers = []
    if environment != expected_environment:
        blockers.append(
            {"code": "observability.environment.mismatch", "message": "metric belongs to another environment"}
        )
    if age < 0:
        blockers.append({"code": "observability.timestamp.future", "message": "metric timestamp is after capture time"})
    elif age > int(profile["freshness_seconds"]):
        blockers.append({"code": "observability.timestamp.stale", "message": "metric observation is stale"})
    metric = profile["metrics"].get(name)
    if metric is None:
        raise OperationalEvidenceError("observability.metric.unsupported", f"unsupported metric {name!r}")
    if unit != metric["unit"] or window != metric["window"]:
        blockers.append(
            {"code": "observability.metric.contract", "message": "unit or window differs from reviewed metric contract"}
        )
    fact = {
        "schema": METRIC_SCHEMA,
        "provider": provider,
        "name": name,
        "value": value,
        "unit": unit,
        "window": window,
        "environment": environment,
        "source": _source(fields.get("source")),
        "timestamp": timestamp,
        "allowed": not blockers,
        "blockers": blockers,
    }
    canonical = json.dumps(fact, sort_keys=True, separators=(",", ":")).encode()
    fact["fingerprint"] = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return fact


def normalize_release_observation(
    payload: dict,
    *,
    expected_release: str,
    expected_revision: str,
    expected_environment: str,
    observed_at: str,
) -> dict:
    required = {"schema", "provider", "kind", "release", "revision", "environment", "status", "timestamp", "source"}
    if not isinstance(payload, dict) or set(payload) != required or payload.get("schema") != RELEASE_SCHEMA:
        raise OperationalEvidenceError("observability.release.fields", "invalid release observation fields")
    kind = str(payload["kind"])
    if kind not in {"deployment", "smoke-test"}:
        raise OperationalEvidenceError("observability.release.kind", f"unsupported release observation {kind!r}")
    release = _identity(payload["release"], "release")
    revision = str(payload["revision"]).casefold()
    expected_revision = str(expected_revision).casefold()
    if not REVISION.fullmatch(revision) or not REVISION.fullmatch(expected_revision):
        raise OperationalEvidenceError("observability.release.revision", "release revision must be a full hash")
    environment = _identity(payload["environment"], "environment")
    timestamp = _timestamp(payload["timestamp"])
    age = (_time(observed_at, "observed_at") - _time(timestamp, "timestamp")).total_seconds()
    blockers = []
    if release != _identity(expected_release, "expected release"):
        blockers.append({"code": "observability.release.mismatch", "message": "observation belongs to another release"})
    if revision != expected_revision:
        blockers.append({"code": "observability.revision.stale", "message": "observation belongs to another revision"})
    if environment != _identity(expected_environment, "expected environment"):
        blockers.append(
            {"code": "observability.environment.mismatch", "message": "observation belongs to another environment"}
        )
    if age < 0:
        blockers.append(
            {"code": "observability.timestamp.future", "message": "observation timestamp is after capture time"}
        )
    elif age > int(load_profile()["freshness_seconds"]):
        blockers.append({"code": "observability.timestamp.stale", "message": "release observation is stale"})
    if payload["status"] != "success":
        blockers.append(
            {"code": "observability.release.unsuccessful", "message": "release observation did not succeed"}
        )
    fact = {
        **payload,
        "provider": _identity(payload["provider"], "provider"),
        "release": release,
        "revision": revision,
        "environment": environment,
        "timestamp": timestamp,
        "source": _source(payload["source"]),
        "allowed": not blockers,
        "blockers": blockers,
    }
    canonical = json.dumps(fact, sort_keys=True, separators=(",", ":")).encode()
    fact["fingerprint"] = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return fact


def evaluate_readiness(
    metrics: list[dict],
    releases: list[dict],
    *,
    expected_release: str,
    expected_revision: str,
    expected_environment: str,
) -> dict:
    profile = load_profile()
    expected_release = _identity(expected_release, "expected release")
    expected_environment = _identity(expected_environment, "expected environment")
    expected_revision = str(expected_revision).casefold()
    if not REVISION.fullmatch(expected_revision):
        raise OperationalEvidenceError("observability.release.revision", "expected revision must be a full hash")
    blockers = []
    selected_metrics = []
    for name in profile["required_metrics"]:
        match = next(
            (
                fact
                for fact in metrics
                if fact.get("name") == name
                and fact.get("environment") == expected_environment
                and fact.get("allowed") is True
            ),
            None,
        )
        if match is None:
            blockers.append({"code": "observability.readiness.metric", "message": f"missing current metric {name}"})
        else:
            selected_metrics.append(match)
    selected_releases = []
    for kind in ("deployment", "smoke-test"):
        match = next(
            (
                fact
                for fact in releases
                if fact.get("kind") == kind
                and fact.get("release") == expected_release
                and fact.get("revision") == expected_revision
                and fact.get("environment") == expected_environment
                and fact.get("allowed") is True
            ),
            None,
        )
        if match is None:
            blockers.append({"code": "observability.readiness.release", "message": f"missing current {kind} evidence"})
        else:
            selected_releases.append(match)
    references = tuple(
        dict.fromkeys([*(f["source"] for f in selected_metrics), *(f["source"] for f in selected_releases)])
    )
    digest_payload = json.dumps(
        {
            "release": expected_release,
            "revision": expected_revision,
            "environment": expected_environment,
            "fingerprints": [fact["fingerprint"] for fact in [*selected_metrics, *selected_releases]],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(digest_payload).hexdigest()
    return {
        "allowed": not blockers,
        "release": expected_release,
        "revision": expected_revision,
        "environment": expected_environment,
        "evidence_refs": references,
        "blockers": blockers,
        "dedupe_key": f"sha256:{digest}",
    }


def core_evidence_input(bundle: dict, *, swarm_id: str, work_id: str, actor_id: str) -> AddEvidenceInput:
    return AddEvidenceInput(
        swarm_id=swarm_id,
        work_id=work_id,
        actor_id=actor_id,
        type="deployment",
        result="success" if bundle["allowed"] else "failure",
        artifact_refs=list(bundle["evidence_refs"]),
        tested_commit=bundle["revision"],
        environment=bundle["environment"],
        dedupe_key=bundle["dedupe_key"],
    )


def control_band_inputs(metric: dict, finding_id: str) -> tuple[AddControlBandInput, EvaluateControlBandInput]:
    if metric.get("allowed") is not True:
        raise OperationalEvidenceError(
            "observability.control-band.blocked", "blocked metric cannot enter a control band"
        )
    contract = load_profile()["metrics"].get(metric.get("name"))
    if contract is None or metric.get("unit") != contract["unit"] or metric.get("window") != contract["window"]:
        raise OperationalEvidenceError(
            "observability.control-band.contract", "metric does not match a reviewed control band"
        )
    band = contract["control_band"]
    return (
        AddControlBandInput(
            id=band["id"],
            metric=metric["name"],
            mean=float(band["mean"]),
            standard_deviation=float(band["standard_deviation"]),
            diagnose_sigma=float(band["diagnose_sigma"]),
            propose_sigma=float(band["propose_sigma"]),
        ),
        EvaluateControlBandInput(band_id=band["id"], id=finding_id, value=metric["value"]),
    )
