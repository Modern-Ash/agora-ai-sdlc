"""AWS-original public-method fidelity rules over repository assets.

The provider is deliberately offline and reads only the supplied repository root.
It converts the checked-in, public-source-derived rule set into generic
`CapabilityFact` values consumed by the compatibility engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from agora_ai_sdlc.compatibility_profiles import load_profile
from agora_ai_sdlc.conformance.compatibility import CapabilityFact
from agora_ai_sdlc.depth_profiles import asset_root

RULES_SCHEMA = "agora-ai-sdlc/aws-original-rules/v1"
RULES_ID = "aws-original"
CHECK_TYPES = {
    "file-exists",
    "files-exist",
    "file-contains-all",
    "front-matter-list-equals",
    "front-matter-list-contains",
}


class AwsOriginalRuleError(ValueError):
    """Stable validation/evaluation error for the AWS-original rule provider."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class FidelityRule:
    capability: str
    classification: str
    pass_checks: tuple[dict, ...]
    partial_checks: tuple[dict, ...]
    evidence: tuple[str, ...]
    remediation: str


@dataclass(frozen=True)
class AdditiveGovernanceRule:
    id: str
    classification: str
    checks: tuple[dict, ...]
    evidence: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class AwsOriginalRules:
    version: str
    base_rules: tuple[FidelityRule, ...]
    additive_governance: tuple[AdditiveGovernanceRule, ...]


@dataclass(frozen=True)
class AdditiveGovernanceResult:
    id: str
    status: str
    evidence: tuple[str, ...]
    reason: str

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "classification": "agora-additive",
            "status": self.status,
            "evidence": list(self.evidence),
            "reason": self.reason,
        }


def _safe_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AwsOriginalRuleError("aws-rule.path", f"{field} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise AwsOriginalRuleError("aws-rule.path", f"{field} must stay inside the repository root")
    return path.as_posix()


def _strings(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise AwsOriginalRuleError("aws-rule.type", f"{field} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise AwsOriginalRuleError("aws-rule.type", f"{field} must not be empty")
    if len(value) != len(set(value)):
        raise AwsOriginalRuleError("aws-rule.duplicate", f"{field} contains duplicate entries")
    return tuple(value)


def _validate_check(raw: object, field: str) -> dict:
    if not isinstance(raw, dict):
        raise AwsOriginalRuleError("aws-rule.type", f"{field} must be a mapping")
    check_type = raw.get("type")
    if check_type not in CHECK_TYPES:
        raise AwsOriginalRuleError("aws-rule.check_type", f"{field} has unknown check type {check_type!r}")
    if check_type == "file-exists":
        if set(raw) != {"type", "path"}:
            raise AwsOriginalRuleError("aws-rule.check_fields", f"{field} has invalid file-exists fields")
        return {"type": check_type, "path": _safe_path(raw["path"], f"{field}.path")}
    if check_type == "files-exist":
        if set(raw) != {"type", "paths"}:
            raise AwsOriginalRuleError("aws-rule.check_fields", f"{field} has invalid files-exist fields")
        paths = _strings(raw["paths"], f"{field}.paths")
        return {"type": check_type, "paths": tuple(_safe_path(path, f"{field}.paths") for path in paths)}
    if check_type == "file-contains-all":
        if set(raw) != {"type", "path", "values"}:
            raise AwsOriginalRuleError("aws-rule.check_fields", f"{field} has invalid file-contains-all fields")
        return {
            "type": check_type,
            "path": _safe_path(raw["path"], f"{field}.path"),
            "values": _strings(raw["values"], f"{field}.values"),
        }
    if set(raw) != {"type", "path", "field", "values"}:
        raise AwsOriginalRuleError("aws-rule.check_fields", f"{field} has invalid front-matter fields")
    front_field = raw["field"]
    if not isinstance(front_field, str) or not front_field:
        raise AwsOriginalRuleError("aws-rule.type", f"{field}.field must be a non-empty string")
    return {
        "type": check_type,
        "path": _safe_path(raw["path"], f"{field}.path"),
        "field": front_field,
        "values": _strings(raw["values"], f"{field}.values", allow_empty=True),
    }


def _checks(value: object, field: str, *, allow_empty: bool = False) -> tuple[dict, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise AwsOriginalRuleError("aws-rule.type", f"{field} must be a list")
    return tuple(_validate_check(check, f"{field}[{index}]") for index, check in enumerate(value))


def parse_rules(contents: str) -> AwsOriginalRules:
    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as error:
        raise AwsOriginalRuleError("aws-rule.syntax", "rules are not valid YAML") from error
    if not isinstance(data, dict):
        raise AwsOriginalRuleError("aws-rule.syntax", "rules top level must be a mapping")
    allowed = {"schema", "id", "version", "profile", "base_rules", "additive_governance"}
    if set(data) != allowed:
        raise AwsOriginalRuleError("aws-rule.fields", "rules must contain exactly the v1 top-level fields")
    if data.get("schema") != RULES_SCHEMA:
        raise AwsOriginalRuleError("aws-rule.schema", f"unsupported rule schema {data.get('schema')!r}")
    if data.get("id") != RULES_ID or data.get("profile") != RULES_ID:
        raise AwsOriginalRuleError("aws-rule.id", "rule id/profile must be aws-original")
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise AwsOriginalRuleError("aws-rule.version", "rule version must be a non-empty string")

    profile = load_profile("aws-original")
    declared = (
        set(profile.required_capabilities) | set(profile.optional_capabilities) | set(profile.unsupported_capabilities)
    )

    raw_base = data["base_rules"]
    if not isinstance(raw_base, list) or not raw_base:
        raise AwsOriginalRuleError("aws-rule.type", "base_rules must be a non-empty list")
    base: list[FidelityRule] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_base):
        if not isinstance(raw, dict):
            raise AwsOriginalRuleError("aws-rule.type", f"base_rules[{index}] must be a mapping")
        expected = {"capability", "classification", "pass", "partial", "evidence", "remediation"}
        if set(raw) != expected or raw.get("classification") != "base-method":
            raise AwsOriginalRuleError("aws-rule.fields", f"base_rules[{index}] has invalid fields/classification")
        capability = raw.get("capability")
        if not isinstance(capability, str) or not capability:
            raise AwsOriginalRuleError("aws-rule.type", f"base_rules[{index}].capability must be a string")
        if capability in seen:
            raise AwsOriginalRuleError("aws-rule.duplicate", f"duplicate base rule for {capability!r}")
        if capability not in declared:
            raise AwsOriginalRuleError("aws-rule.undeclared", f"rule capability {capability!r} is not in profile")
        seen.add(capability)
        evidence = tuple(
            _safe_path(path, f"base_rules[{index}].evidence") for path in _strings(raw["evidence"], "evidence")
        )
        remediation = raw.get("remediation")
        if not isinstance(remediation, str) or not remediation.strip():
            raise AwsOriginalRuleError("aws-rule.type", f"base_rules[{index}].remediation must be non-empty")
        base.append(
            FidelityRule(
                capability=capability,
                classification="base-method",
                pass_checks=_checks(raw["pass"], f"base_rules[{index}].pass"),
                partial_checks=_checks(raw["partial"], f"base_rules[{index}].partial", allow_empty=True),
                evidence=evidence,
                remediation=remediation,
            )
        )

    missing = sorted(declared - seen)
    if missing:
        raise AwsOriginalRuleError("aws-rule.missing", f"profile capabilities without base rules: {', '.join(missing)}")

    raw_additive = data["additive_governance"]
    if not isinstance(raw_additive, list):
        raise AwsOriginalRuleError("aws-rule.type", "additive_governance must be a list")
    additive: list[AdditiveGovernanceRule] = []
    additive_ids: set[str] = set()
    for index, raw in enumerate(raw_additive):
        if not isinstance(raw, dict):
            raise AwsOriginalRuleError("aws-rule.type", f"additive_governance[{index}] must be a mapping")
        expected = {"id", "classification", "checks", "evidence", "reason"}
        if set(raw) != expected or raw.get("classification") != "agora-additive":
            raise AwsOriginalRuleError(
                "aws-rule.fields", f"additive_governance[{index}] has invalid fields/classification"
            )
        rule_id = raw.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise AwsOriginalRuleError("aws-rule.type", f"additive_governance[{index}].id must be a string")
        if rule_id in additive_ids or rule_id in declared:
            raise AwsOriginalRuleError("aws-rule.duplicate", f"duplicate/colliding additive rule {rule_id!r}")
        additive_ids.add(rule_id)
        evidence = tuple(
            _safe_path(path, f"additive_governance[{index}].evidence") for path in _strings(raw["evidence"], "evidence")
        )
        reason = raw.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise AwsOriginalRuleError("aws-rule.type", f"additive_governance[{index}].reason must be non-empty")
        additive.append(
            AdditiveGovernanceRule(
                id=rule_id,
                classification="agora-additive",
                checks=_checks(raw["checks"], f"additive_governance[{index}].checks"),
                evidence=evidence,
                reason=reason,
            )
        )

    return AwsOriginalRules(version, tuple(base), tuple(additive))


def load_rules() -> AwsOriginalRules:
    path = asset_root("contracts") / "conformance" / "aws-original-rules-v1.yaml"
    if not path.is_file():
        raise AwsOriginalRuleError("aws-rule.file", f"rules file not found: {path}")
    return parse_rules(path.read_text(encoding="utf-8"))


def _front_matter(path: Path) -> dict:
    if not path.is_file():
        return {}
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        return {}
    try:
        end = lines.index("---", 1)
        front = yaml.safe_load("\n".join(lines[1:end])) or {}
    except (ValueError, yaml.YAMLError):
        return {}
    return front if isinstance(front, dict) else {}


def _check(root: Path, check: dict) -> bool:
    kind = check["type"]
    if kind == "file-exists":
        return (root / check["path"]).is_file()
    if kind == "files-exist":
        return all((root / path).is_file() for path in check["paths"])
    if kind == "file-contains-all":
        path = root / check["path"]
        if not path.is_file():
            return False
        text = path.read_text(encoding="utf-8")
        return all(value in text for value in check["values"])
    front = _front_matter(root / check["path"])
    value = front.get(check["field"])
    if not isinstance(value, list):
        return False
    if kind == "front-matter-list-equals":
        return value == list(check["values"])
    return all(item in value for item in check["values"])


def _all(root: Path, checks: tuple[dict, ...]) -> bool:
    return bool(checks) and all(_check(root, check) for check in checks)


def _evidence(root: Path, paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"repo://{path}" for path in paths if (root / path).exists())


def derive_facts(root: Path) -> tuple[CapabilityFact, ...]:
    """Derive generic facts for the aws-original profile from one repository root."""

    root = Path(root)
    rules = load_rules()
    profile = load_profile("aws-original")
    optional = set(profile.optional_capabilities)
    facts: list[CapabilityFact] = []
    for rule in rules.base_rules:
        if _all(root, rule.pass_checks):
            status = "PASS"
            reason = "All fidelity checks for this capability are satisfied."
        elif _all(root, rule.partial_checks):
            status = "PARTIAL"
            reason = "Some method semantics are represented, but the full fidelity rule is not satisfied."
        elif rule.capability in optional:
            continue
        else:
            status = "FAIL"
            reason = "Required method fidelity checks are not satisfied."
        facts.append(
            CapabilityFact(
                capability=rule.capability,
                status=status,
                evidence=_evidence(root, rule.evidence),
                reason=reason,
                remediation=None if status == "PASS" else rule.remediation,
            )
        )
    return tuple(facts)


def derive_additive_governance(root: Path) -> tuple[AdditiveGovernanceResult, ...]:
    """Report Agora additions separately; these results never affect AWS base fidelity."""

    root = Path(root)
    rules = load_rules()
    results = []
    for rule in rules.additive_governance:
        status = "PASS" if _all(root, rule.checks) else "FAIL"
        results.append(
            AdditiveGovernanceResult(
                id=rule.id,
                status=status,
                evidence=_evidence(root, rule.evidence),
                reason=rule.reason,
            )
        )
    return tuple(results)
