"""Generate evidence-backed compatibility documentation for Marketplace use."""

from __future__ import annotations

from pathlib import Path

from agora_ai_sdlc.compatibility_profiles import load_profile
from agora_ai_sdlc.conformance.aws_original import derive_additive_governance, derive_facts
from agora_ai_sdlc.conformance.compatibility import evaluate
from agora_ai_sdlc.conformance.lg_enterprise import FACTS_SOURCE as LG_FACTS_SOURCE
from agora_ai_sdlc.conformance.lg_enterprise import derive_facts as derive_lg_facts

GENERATED_RELATIVE = Path("docs/commercial/marketplace/compatibility-evidence.md")

FORBIDDEN_IMPLICATIONS = (
    "aws certified",
    "aws-certified",
    "certified by aws",
    "endorsed by aws",
    "endorsed by lg",
    "lg certified",
    "lg-certified",
)


def _link(path: str) -> str:
    return f"[{path}](../../../{path})"


def _items(values: list[str]) -> str:
    return ", ".join(values) if values else "—"


def _grouped_statuses(report) -> dict[str, list[str]]:
    grouped = {"PASS": [], "PARTIAL": [], "FAIL": [], "NOT_APPLICABLE": []}
    for result in report.results:
        grouped[result.status].append(result.capability)
    return {status: sorted(values) for status, values in grouped.items()}


def generate(root: Path) -> str:
    """Render the checked-in Marketplace compatibility evidence matrix."""

    root = Path(root)
    aws_profile = load_profile("aws-original")
    aws_report = evaluate(aws_profile, derive_facts(root), facts_source="derived:aws-original-rules/v1")
    aws = _grouped_statuses(aws_report)

    lg_profile = load_profile("lg-enterprise")
    lg_report = evaluate(lg_profile, derive_lg_facts(root), facts_source=LG_FACTS_SOURCE)
    lg = _grouped_statuses(lg_report)
    lg_required = sorted(lg_profile.required_capabilities)

    agora_results = derive_additive_governance(root)
    agora_pass = sorted(result.id for result in agora_results if result.status == "PASS")
    agora_fail = sorted(result.id for result in agora_results if result.status == "FAIL")

    aws_evidence = ", ".join(
        (
            _link("contracts/conformance/aws-original-rules-v1.yaml"),
            _link("tests/fixtures/conformance/aws-original/current.yaml"),
            _link("tests/conformance/test_aws_original_rules.py"),
        )
    )
    lg_evidence = ", ".join(
        (
            _link("profiles/compatibility/lg-enterprise/profile.yaml"),
            _link("src/agora_ai_sdlc/conformance/lg_enterprise.py"),
            _link("tests/conformance/test_lg_enterprise_rules.py"),
        )
    )
    agora_evidence = ", ".join(
        (
            _link("contracts/conformance/aws-original-rules-v1.yaml"),
            _link("tests/conformance/test_aws_original_rules.py"),
        )
    )

    lines = [
        "<!-- GENERATED FILE: run uv run python scripts/check_marketplace_evidence.py --write -->",
        "# Compatibility evidence matrix",
        "",
        "This file is generated from checked-in compatibility contracts and executable conformance rules.",
        "It is release evidence, not a certification, affiliation, partnership, or endorsement claim.",
        "",
        "## Matrix",
        "",
        "| Evidence dimension | AWS-original | LG-enterprise | Agora-open |",
        "| --- | --- | --- | --- |",
        (
            f"| Current result | **{aws_report.overall_status}** (executable repository conformance) | "
            f"**{lg_report.overall_status}** (executable repository conformance against the public profile) | "
            f"**{'PASS' if not agora_fail else 'FAIL'}** (additive governance only) |"
        ),
        f"| PASS | {_items(aws['PASS'])} | {_items(lg['PASS'])} | {_items(agora_pass)} |",
        f"| PARTIAL | {_items(aws['PARTIAL'])} | {_items(lg['PARTIAL'])} | — |",
        f"| FAIL | {_items(aws['FAIL'])} | {_items(lg['FAIL'])} | {_items(agora_fail)} |",
        f"| NOT_APPLICABLE / optional | {_items(aws['NOT_APPLICABLE'])} | {_items(lg['NOT_APPLICABLE'])} | — |",
        f"| Required target capabilities | Derived by executable rules | {_items(lg_required)} | Additive controls, not base-method requirements |",
        f"| Evidence | {aws_evidence} | {lg_evidence} | {agora_evidence} |",
        (
            "| Boundary | Public-method fidelity only; PARTIAL/FAIL remain visible | "
            "Public-profile implementation evidence only; no private/proprietary LG behavior is modeled | "
            "Agora-specific governance is never counted as AWS-original fidelity |"
        ),
        "",
        "## Claim boundaries",
        "",
        "- AWS-original statuses come from the repository-derived conformance provider and cannot be promoted by editing this document.",
        "- LG-enterprise statuses come from the repository-derived public-profile provider; PARTIAL/FAIL remain visible and no proprietary LG behavior is inferred.",
        "- Agora-open reports additive governance such as fail-closed gates, independent review, provider neutrality, and model/session provenance; those controls do not upgrade AWS-original fidelity.",
        "- Proprietary or non-public AWS/LG prompts, source code, scoring, implementation details, partner status, certification, sponsorship, or endorsement are not evaluated or claimed.",
        "- Marketplace and release copy must preserve current PARTIAL/FAIL states and link back to this generated evidence.",
        "",
        "## Regeneration",
        "",
        "Run: uv run python scripts/check_marketplace_evidence.py --write",
        "",
        "CI runs the checker without --write and fails when this file is missing or differs from regeneration.",
        "",
    ]
    rendered = "\n".join(lines)

    lowered = rendered.casefold()
    for phrase in FORBIDDEN_IMPLICATIONS:
        if phrase in lowered:
            raise ValueError(f"marketplace.claim_boundary: forbidden implication {phrase!r}")
    return rendered


def check(root: Path) -> tuple[bool, str]:
    expected = generate(root)
    path = Path(root) / GENERATED_RELATIVE
    if not path.is_file():
        return False, f"missing generated evidence matrix: {GENERATED_RELATIVE}"
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"generated evidence matrix is stale: {GENERATED_RELATIVE}"
    return True, "compatibility evidence matrix is current"


def write(root: Path) -> Path:
    root = Path(root)
    path = root / GENERATED_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate(root), encoding="utf-8")
    return path
