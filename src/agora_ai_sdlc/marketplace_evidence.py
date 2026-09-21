"""Generate evidence-backed compatibility documentation for Marketplace use."""

from __future__ import annotations

from pathlib import Path

from agora_ai_sdlc.compatibility_profiles import load_profile
from agora_ai_sdlc.conformance.aws_original import derive_additive_governance, derive_facts
from agora_ai_sdlc.conformance.compatibility import evaluate

GENERATED_RELATIVE = Path("docs/commercial/marketplace/compatibility-evidence.md")
LG_PROFILE_EVIDENCE = "profiles/compatibility/lg-enterprise/profile.yaml"

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


def _status_counts(values: list[str]) -> str:
    order = ("PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE")
    counts = {status: values.count(status) for status in order}
    return ", ".join(f"{status}={counts[status]}" for status in order if counts[status])


def _lg_requirements() -> dict[str, str]:
    profile = load_profile("lg-enterprise")
    requirements: dict[str, str] = {}
    for capability in profile.required_capabilities:
        requirements[capability] = "TARGET_REQUIRED"
    for capability in profile.optional_capabilities:
        requirements[capability] = "TARGET_OPTIONAL"
    for capability in profile.unsupported_capabilities:
        requirements[capability] = "TARGET_UNSUPPORTED"
    return requirements


def generate(root: Path) -> str:
    """Render the checked-in Marketplace compatibility evidence matrix."""

    root = Path(root)
    aws_profile = load_profile("aws-original")
    aws_report = evaluate(
        aws_profile,
        derive_facts(root),
        facts_source="derived:aws-original-rules/v1",
    )
    aws = {result.capability: result for result in aws_report.results}
    lg_profile = load_profile("lg-enterprise")
    lg = _lg_requirements()
    agora_results = {result.id: result for result in derive_additive_governance(root)}

    row_ids = sorted(set(aws) | set(lg) | set(agora_results))
    aws_statuses = [result.status for result in aws.values()]
    agora_statuses = [result.status for result in agora_results.values()]

    lines = [
        "<!-- GENERATED FILE: run uv run python scripts/check_marketplace_evidence.py --write -->",
        "# Compatibility evidence matrix",
        "",
        "This document is generated from checked-in compatibility contracts and conformance rules.",
        "Do not edit it by hand. It is release evidence, not a certification, affiliation, partnership, or endorsement claim.",
        "",
        "## Snapshot",
        "",
        f"- **AWS-original public method:** {_status_counts(aws_statuses)}; overall **{aws_report.overall_status}**.",
        (
            f"- **LG-enterprise public presentation:** {len(lg_profile.required_capabilities)} required "
            f"target capabilities and {len(lg_profile.optional_capabilities)} optional target capabilities. "
            "No LG implementation conformance provider exists yet, so this column never reports PASS/PARTIAL/FAIL."
        ),
        f"- **Agora-open additive governance:** {_status_counts(agora_statuses)}. These results do not affect AWS fidelity.",
        "",
        "## Status vocabulary",
        "",
        "- PASS, PARTIAL, FAIL, NOT_APPLICABLE: executable AWS-original conformance result.",
        "- TARGET_REQUIRED, TARGET_OPTIONAL, TARGET_UNSUPPORTED: public LG-enterprise profile declaration only, not implementation conformance.",
        "- —: the row is not part of that column's current contract.",
        "",
        "## Matrix",
        "",
        "| Capability / control | AWS-original | LG-enterprise | Agora-open | Evidence and boundary |",
        "| --- | --- | --- | --- | --- |",
    ]

    for row_id in row_ids:
        aws_result = aws.get(row_id)
        lg_status = lg.get(row_id, "—")
        agora_result = agora_results.get(row_id)

        aws_status = aws_result.status if aws_result else "—"
        agora_status = agora_result.status if agora_result else "—"

        notes: list[str] = []
        if aws_result:
            if aws_result.evidence:
                notes.append("AWS evidence: " + ", ".join(_link(ref.removeprefix("repo://")) for ref in aws_result.evidence))
            else:
                notes.append("AWS evidence: none recorded")
            if aws_result.remediation:
                notes.append("AWS remediation: " + aws_result.remediation)
        if row_id in lg:
            notes.append("LG target source: " + _link(LG_PROFILE_EVIDENCE))
        if agora_result:
            if agora_result.evidence:
                notes.append(
                    "Agora evidence: " + ", ".join(_link(ref.removeprefix("repo://")) for ref in agora_result.evidence)
                )
            notes.append("Agora boundary: additive governance; excluded from AWS base-method fidelity")

        lines.append(
            f"| {row_id} | {aws_status} | {lg_status} | {agora_status} | {'<br>'.join(notes)} |"
        )

    lines.extend(
        [
            "",
            "## Deliberate differences and non-evaluated behavior",
            "",
            "- Agora's fail-closed gates, independent review, provider neutrality, and model/session provenance are additive governance. They are reported in the Agora-open column and are not used to upgrade AWS-original fidelity.",
            "- The LG-enterprise column records only the public target contract. Until a dedicated rule provider is implemented, no LG row is represented as an implementation PASS.",
            "- Proprietary, private, or non-public AWS/LG prompts, scoring, source code, implementation details, partner status, certification, or endorsement are not evaluated or claimed.",
            "- A PARTIAL or FAIL AWS result must remain visible in Marketplace/release material; documentation may not rewrite it as full compatibility.",
            "",
            "## Claim use",
            "",
            "Buyer-facing compatibility language must reference this generated matrix and preserve its current statuses and boundaries. "
            "The repository verification pipeline regenerates the matrix and fails if the checked-in copy diverges.",
            "",
        ]
    )
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
