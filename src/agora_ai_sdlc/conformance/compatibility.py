"""Generic compatibility conformance evaluation.

This module intentionally contains no AWS-, LG-, cloud-, model- or provider-specific
rules. It evaluates versioned compatibility profiles against explicit project/repo
capability facts. Method-specific fact derivation belongs in later rule/provider
modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from agora_ai_sdlc.compatibility_profiles import (
    CompatibilityProfile,
    CompatibilityProfileError,
    load_profile,
)

FACTS_SCHEMA = "agora-ai-sdlc/conformance-facts/v1"
RESULT_SCHEMA = "agora-ai-sdlc/conformance-result/v1"
STATUSES = ("PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE")
DEFAULT_FACTS_RELATIVE = Path(".agora") / "ai-sdlc" / "conformance-facts.yaml"


class ConformanceError(ValueError):
    """Stable machine-readable conformance input/evaluation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class CapabilityFact:
    capability: str
    status: str
    evidence: tuple[str, ...]
    reason: str
    remediation: str | None = None


@dataclass(frozen=True)
class CapabilityResult:
    capability: str
    requirement: str
    status: str
    evidence: tuple[str, ...]
    reason: str
    source_contract_version: str
    remediation: str | None

    def snapshot(self) -> dict:
        return {
            "capability": self.capability,
            "requirement": self.requirement,
            "status": self.status,
            "evidence": list(self.evidence),
            "reason": self.reason,
            "source_contract_version": self.source_contract_version,
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class ConformanceReport:
    profile_id: str
    profile_name: str
    profile_version: str
    overall_status: str
    facts_source: str | None
    results: tuple[CapabilityResult, ...]

    @property
    def has_failures(self) -> bool:
        return any(result.status == "FAIL" for result in self.results)

    def snapshot(self) -> dict:
        return {
            "schema": RESULT_SCHEMA,
            "profile": {
                "id": self.profile_id,
                "name": self.profile_name,
                "version": self.profile_version,
            },
            "overall_status": self.overall_status,
            "has_failures": self.has_failures,
            "facts_source": self.facts_source,
            "results": [result.snapshot() for result in self.results],
        }


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConformanceError("conformance.fact_type", f"{field!r} must be a non-empty string")
    return value


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ConformanceError("conformance.fact_type", f"{field!r} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise ConformanceError("conformance.fact_duplicate_evidence", f"duplicate entries in {field!r}")
    return tuple(value)


def parse_facts(contents: str) -> tuple[CapabilityFact, ...]:
    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as error:
        raise ConformanceError("conformance.fact_syntax", "facts file is not valid YAML") from error
    if not isinstance(data, dict):
        raise ConformanceError("conformance.fact_syntax", "facts top level must be a mapping")
    if data.get("schema") != FACTS_SCHEMA:
        raise ConformanceError(
            "conformance.fact_schema",
            f"unsupported facts schema {data.get('schema')!r}; expected {FACTS_SCHEMA}",
        )
    unknown = sorted(set(data) - {"schema", "facts"})
    if unknown:
        raise ConformanceError("conformance.fact_unknown_field", f"unknown facts fields: {', '.join(unknown)}")
    raw_facts = data.get("facts")
    if not isinstance(raw_facts, list):
        raise ConformanceError("conformance.fact_type", "'facts' must be a list")

    facts: list[CapabilityFact] = []
    seen: set[str] = set()
    allowed_fields = {"capability", "status", "evidence", "reason", "remediation"}
    for index, raw in enumerate(raw_facts):
        if not isinstance(raw, dict):
            raise ConformanceError("conformance.fact_type", f"facts[{index}] must be a mapping")
        unknown_fact = sorted(set(raw) - allowed_fields)
        if unknown_fact:
            raise ConformanceError(
                "conformance.fact_unknown_field",
                f"facts[{index}] unknown fields: {', '.join(unknown_fact)}",
            )
        for field in ("capability", "status", "reason"):
            if field not in raw:
                raise ConformanceError("conformance.fact_missing", f"facts[{index}] missing field {field!r}")
        capability = _string(raw["capability"], f"facts[{index}].capability")
        if capability in seen:
            raise ConformanceError("conformance.fact_duplicate", f"duplicate fact for capability {capability!r}")
        seen.add(capability)
        status = _string(raw["status"], f"facts[{index}].status")
        if status not in STATUSES:
            raise ConformanceError(
                "conformance.fact_status", f"invalid status {status!r}; expected one of {', '.join(STATUSES)}"
            )
        evidence = _string_list(raw.get("evidence", []), f"facts[{index}].evidence")
        reason = _string(raw["reason"], f"facts[{index}].reason")
        remediation_raw = raw.get("remediation")
        remediation = None if remediation_raw is None else _string(remediation_raw, f"facts[{index}].remediation")
        facts.append(CapabilityFact(capability, status, evidence, reason, remediation))
    return tuple(facts)


def load_facts(path: Path) -> tuple[CapabilityFact, ...]:
    if not path.is_file():
        raise ConformanceError("conformance.fact_file", f"facts file not found: {path}")
    return parse_facts(path.read_text(encoding="utf-8"))


def _overall(results: tuple[CapabilityResult, ...]) -> str:
    statuses = {result.status for result in results}
    if "FAIL" in statuses:
        return "FAIL"
    if "PARTIAL" in statuses:
        return "PARTIAL"
    if "PASS" in statuses:
        return "PASS"
    return "NOT_APPLICABLE"


def _default_remediation(capability: str, status: str) -> str | None:
    if status == "FAIL":
        return f"Provide complete project evidence for required capability {capability!r}."
    if status == "PARTIAL":
        return f"Complete or strengthen project evidence for capability {capability!r}."
    return None


def evaluate(
    profile: CompatibilityProfile,
    facts: tuple[CapabilityFact, ...],
    *,
    facts_source: str | None = None,
) -> ConformanceReport:
    """Evaluate one profile against already-parsed facts."""

    required = set(profile.required_capabilities)
    optional = set(profile.optional_capabilities)
    unsupported = set(profile.unsupported_capabilities)
    declared = required | optional | unsupported
    by_capability = {fact.capability: fact for fact in facts}

    unknown = sorted(set(by_capability) - declared)
    if unknown:
        raise ConformanceError(
            "conformance.fact_unknown_capability",
            f"facts contain capabilities not declared by profile {profile.id!r}: {', '.join(unknown)}",
        )

    results: list[CapabilityResult] = []
    for requirement, capabilities in (
        ("required", profile.required_capabilities),
        ("optional", profile.optional_capabilities),
        ("unsupported", profile.unsupported_capabilities),
    ):
        for capability in sorted(capabilities):
            fact = by_capability.get(capability)

            if requirement == "unsupported":
                evidence = () if fact is None else fact.evidence
                reason = (
                    "Compatibility profile marks this capability unsupported."
                    if fact is None
                    else f"Compatibility profile marks this capability unsupported. Declared fact: {fact.reason}"
                )
                results.append(
                    CapabilityResult(
                        capability=capability,
                        requirement=requirement,
                        status="NOT_APPLICABLE",
                        evidence=evidence,
                        reason=reason,
                        source_contract_version=profile.version,
                        remediation=None,
                    )
                )
                continue

            if fact is None:
                if requirement == "required":
                    results.append(
                        CapabilityResult(
                            capability=capability,
                            requirement=requirement,
                            status="FAIL",
                            evidence=(),
                            reason="No project capability fact was supplied.",
                            source_contract_version=profile.version,
                            remediation=_default_remediation(capability, "FAIL"),
                        )
                    )
                else:
                    results.append(
                        CapabilityResult(
                            capability=capability,
                            requirement=requirement,
                            status="NOT_APPLICABLE",
                            evidence=(),
                            reason="Optional capability has no declared project fact.",
                            source_contract_version=profile.version,
                            remediation=None,
                        )
                    )
                continue

            status = fact.status
            reason = fact.reason
            if requirement == "required" and status == "NOT_APPLICABLE":
                status = "FAIL"
                reason = f"Required capability cannot be NOT_APPLICABLE. Declared reason: {fact.reason}"
            remediation = fact.remediation
            if status in {"FAIL", "PARTIAL"} and remediation is None:
                remediation = _default_remediation(capability, status)
            results.append(
                CapabilityResult(
                    capability=capability,
                    requirement=requirement,
                    status=status,
                    evidence=fact.evidence,
                    reason=reason,
                    source_contract_version=profile.version,
                    remediation=remediation,
                )
            )

    frozen = tuple(results)
    return ConformanceReport(
        profile_id=profile.id,
        profile_name=profile.name,
        profile_version=profile.version,
        overall_status=_overall(frozen),
        facts_source=facts_source,
        results=frozen,
    )


def evaluate_project(
    profile_id: str,
    *,
    project_root: Path | None = None,
    facts_path: Path | None = None,
) -> ConformanceReport:
    """Evaluate a packaged compatibility profile against local project facts."""

    try:
        profile = load_profile(profile_id)
    except CompatibilityProfileError as error:
        raise ConformanceError("conformance.profile", str(error)) from error

    root = Path.cwd() if project_root is None else Path(project_root)
    if facts_path is not None:
        path = Path(facts_path)
        facts = load_facts(path)
        source = str(path)
    else:
        path = root / DEFAULT_FACTS_RELATIVE
        if path.is_file():
            facts = load_facts(path)
            source = str(path)
        else:
            facts = ()
            source = None
    return evaluate(profile, facts, facts_source=source)


def render_human(report: ConformanceReport) -> str:
    """Render a stable, concise human-readable report."""

    lines = [
        f"{report.profile_name} ({report.profile_id} v{report.profile_version})",
        f"Overall: {report.overall_status}",
    ]
    if report.facts_source:
        lines.append(f"Facts: {report.facts_source}")
    else:
        lines.append("Facts: none")
    lines.append("")
    for result in report.results:
        lines.append(f"{result.status:14} {result.capability} [{result.requirement}]")
        lines.append(f"  reason: {result.reason}")
        if result.evidence:
            lines.append(f"  evidence: {', '.join(result.evidence)}")
        if result.remediation:
            lines.append(f"  remediation: {result.remediation}")
        lines.append(f"  contract: {result.source_contract_version}")
    return "\n".join(lines)
