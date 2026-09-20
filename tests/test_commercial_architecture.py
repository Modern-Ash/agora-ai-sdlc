import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
COMMERCIAL = ROOT / "docs" / "commercial"
ARCHITECTURE = (COMMERCIAL / "reference-architecture.md").read_text(encoding="utf-8")
RESPONSIBILITY = (COMMERCIAL / "security-and-responsibility.md").read_text(encoding="utf-8")


def headings(text: str) -> set[str]:
    return set(re.findall(r"^##+ (.+)$", text, re.MULTILINE))


def test_reference_architecture_has_neutral_primary_diagram_and_all_patterns():
    required = {
        "Primary technology-neutral architecture",
        "Ownership and trust boundaries",
        "Deployment patterns",
        "Developer workstation and local execution",
        "CI automation",
        "Self-managed enterprise",
        "Replaceable components",
        "Failure and recovery paths",
        "Optional deployment mappings",
        "Verification anchors",
    }
    assert required <= headings(ARCHITECTURE)

    diagram = re.search(r"```mermaid\n(.+?)```", ARCHITECTURE, re.DOTALL)
    assert diagram
    assert not re.search(r"\b(?:aws|azure|gcp|amazon|google cloud)\b", diagram.group(1), re.IGNORECASE)
    for boundary in ("Agora Core", "AI-SDLC flavor", "External tools", "Optional Studio"):
        assert boundary in diagram.group(1)

    mappings = ARCHITECTURE.split("## Optional deployment mappings", 1)[1]
    for deployment in ("AWS example", "Azure example", "GCP example", "On-premises"):
        assert deployment in mappings
    assert "illustrative, not bundled adapters, endorsements, required products" in mappings


def test_architecture_preserves_product_boundaries_and_recovery_paths():
    lower = ARCHITECTURE.casefold()
    assert "core alone decides whether its lifecycle transition contract is satisfied" in lower
    assert "does not parse method packs, read or write `.agora/`" in lower
    assert "there is no control plane transaction across repositories" in lower
    assert "cli/core operations continue" in lower
    assert "signed forward release" in lower

    failure_rows = [
        line
        for line in ARCHITECTURE.split("## Failure and recovery paths", 1)[1].split("\n## ", 1)[0].splitlines()
        if line.startswith("|")
    ][2:]
    assert len(failure_rows) >= 8
    assert all(row.count("|") == 4 for row in failure_rows)


def test_shared_responsibility_covers_required_controls_and_control_types():
    required = {
        "Control language",
        "Shared-responsibility matrix",
        "Data and secret boundary",
        "Responsibility by deployment pattern",
        "Incident and recovery model",
        "Service boundary",
    }
    assert required <= headings(RESPONSIBILITY)
    for control_type in (
        "Agora enforcement",
        "Flavor validation",
        "Deployment evidence",
        "Deployment responsibility",
    ):
        assert f"**{control_type}**" in RESPONSIBILITY
    for topic in (
        "Human and actor identity",
        "Credentials and private keys",
        "Infrastructure isolation",
        "Data residency, privacy, and retention",
        "Provider and model terms",
        "Backups and recovery",
        "Monitoring and incident response",
    ):
        assert f"| {topic} |" in RESPONSIBILITY


def test_documents_reject_unsupported_security_and_hosting_claims():
    copy = f"{ARCHITECTURE}\n{RESPONSIBILITY}".casefold()
    prohibited = {
        "studio writes `.agora`",
        "agora stores credentials",
        "hosted control plane is available",
        "aws is required",
        "certified compliant",
        "guarantees compliance",
    }
    assert not any(claim in copy for claim in prohibited)
    assert "not certification" in copy
    assert "future control plane" in copy


def test_reference_documents_are_linked_and_local_links_resolve():
    overview = (COMMERCIAL / "README.md").read_text(encoding="utf-8")
    assert "[Vendor-neutral reference architecture](reference-architecture.md)" in overview
    assert "[Security and shared responsibility](security-and-responsibility.md)" in overview

    for document in (COMMERCIAL / "reference-architecture.md", COMMERCIAL / "security-and-responsibility.md"):
        text = document.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            if "://" not in target:
                assert (document.parent / target).resolve().exists(), (document, target)
