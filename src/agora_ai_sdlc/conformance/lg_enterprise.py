"""Offline LG-enterprise public-profile conformance over repository assets.

This provider evaluates only public profile capabilities implemented by Agora AI-SDLC.
It does not model proprietary LG implementation details and has no vendor/runtime dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agora_ai_sdlc.conformance.compatibility import CapabilityFact
from agora_ai_sdlc.depth_profiles import asset_root

FACTS_SOURCE = "derived:lg-enterprise-rules/v1"


@dataclass(frozen=True)
class Rule:
    capability: str
    pass_paths: tuple[str, ...]
    partial_paths: tuple[str, ...] = ()
    remediation: str | None = None


RULES = (
    Rule(
        "organizational-readiness",
        ("templates/readiness-assessment.md", "profiles/compatibility/lg-enterprise/profile.yaml"),
        remediation="Provide an explicit organizational-readiness assessment contract.",
    ),
    Rule(
        "technical-setup",
        ("src/agora_ai_sdlc/enterprise.py", "profiles/enterprise/profile.yaml"),
        remediation="Provide reviewed enterprise bootstrap/setup evidence.",
    ),
    Rule(
        "ideation",
        ("templates/product-intent.md", "src/agora_ai_sdlc/presentation.py"),
        remediation="Provide an explicit ideation/Intent artifact and presentation mapping.",
    ),
    Rule(
        "review-gates",
        ("src/agora_ai_sdlc/enterprise_reviews.py", "profiles/reviews/enterprise.yaml"),
        remediation="Provide the complete enterprise review-gate policy bundle.",
    ),
    Rule(
        "quality-governance",
        ("src/agora_ai_sdlc/independent_review.py", "src/agora_ai_sdlc/enterprise_reviews.py"),
        remediation="Provide independent-review and quality-governance enforcement.",
    ),
    Rule(
        "risk-issue-management",
        (),
        ("profiles/pathways/regulated-change.yaml", "profiles/reviews/enterprise.yaml"),
        "Add a dedicated provider-neutral risk/issue register contract and evaluator.",
    ),
    Rule(
        "change-configuration-management",
        ("src/agora_ai_sdlc/change_management.py", "templates/change-request.md"),
        remediation="Provide governed change/configuration artifact semantics.",
    ),
    Rule(
        "security-compliance",
        ("src/agora_ai_sdlc/security_findings.py", "profiles/integrations/security/profile.yaml"),
        remediation="Provide normalized security/compliance evidence and policy.",
    ),
    Rule(
        "documentation",
        ("templates/unit-of-work.md", "templates/requirements.md"),
        remediation="Document the durable enterprise artifact contracts.",
    ),
    Rule(
        "traceability",
        ("src/agora_ai_sdlc/artifacts.py", "src/agora_ai_sdlc/context_graph.py"),
        remediation="Provide forward/backward artifact traceability.",
    ),
    Rule(
        "test-design",
        ("src/agora_ai_sdlc/enterprise_controls.py", "templates/test-strategy.md"),
        remediation="Provide test-design policy and test-strategy evidence.",
    ),
    Rule(
        "code-review",
        ("src/agora_ai_sdlc/enterprise_controls.py", "src/agora_ai_sdlc/independent_review.py"),
        remediation="Provide reviewer separation and required review evidence.",
    ),
    Rule(
        "domain-knowledge",
        ("src/agora_ai_sdlc/domain_knowledge.py", "contracts/enterprise/domain-knowledge-source-v1.schema.json"),
        remediation="Provide provider-neutral domain-knowledge source contracts.",
    ),
    Rule(
        "operational-rules",
        ("src/agora_ai_sdlc/operational_evidence.py", "templates/operational-readiness.md"),
        remediation="Provide operational evidence and governed remediation rules.",
    ),
    Rule(
        "cross-repository-impact",
        ("src/agora_ai_sdlc/impact_analysis.py", "templates/impact-analysis.md"),
        remediation="Provide approved cross-repository impact-analysis semantics.",
    ),
)


def _resolve(root: Path, path: str, *, packaged_fallback: bool) -> Path:
    repository = root / path
    if repository.is_file() or not packaged_fallback:
        return repository
    if path.startswith("src/agora_ai_sdlc/"):
        return Path(__file__).parents[1] / path.removeprefix("src/agora_ai_sdlc/")
    first, _, remainder = path.partition("/")
    if first in {"profiles", "templates", "contracts", "policies", "samples", "registry"}:
        return asset_root(first) / remainder
    return repository


def _present(root: Path, paths: tuple[str, ...], *, packaged_fallback: bool) -> bool:
    return bool(paths) and all(_resolve(root, path, packaged_fallback=packaged_fallback).is_file() for path in paths)


def _evidence(root: Path, paths: tuple[str, ...], *, packaged_fallback: bool) -> tuple[str, ...]:
    return tuple(
        f"repo://{path}" for path in paths if _resolve(root, path, packaged_fallback=packaged_fallback).is_file()
    )


def derive_facts(root: Path, *, packaged_fallback: bool = False) -> tuple[CapabilityFact, ...]:
    """Derive lg-enterprise capability facts from a repository root or packaged distribution."""

    root = Path(root)
    facts: list[CapabilityFact] = []
    for rule in RULES:
        if _present(root, rule.pass_paths, packaged_fallback=packaged_fallback):
            status = "PASS"
            paths = rule.pass_paths
            reason = "Public enterprise capability has complete checked-in implementation evidence."
        elif _present(root, rule.partial_paths, packaged_fallback=packaged_fallback):
            status = "PARTIAL"
            paths = rule.partial_paths
            reason = "Public enterprise capability is represented, but a dedicated complete contract is still missing."
        else:
            status = "FAIL"
            paths = (*rule.pass_paths, *rule.partial_paths)
            reason = "Required public enterprise capability implementation evidence is missing."
        facts.append(
            CapabilityFact(
                capability=rule.capability,
                status=status,
                evidence=_evidence(root, paths, packaged_fallback=packaged_fallback),
                reason=reason,
                remediation=None if status == "PASS" else rule.remediation,
            )
        )
    return tuple(facts)
