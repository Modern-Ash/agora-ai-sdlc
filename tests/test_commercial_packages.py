import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
COMMERCIAL = ROOT / "docs" / "commercial"
PACKAGES = {
    "assessment.md": "ai-sdlc-assessment",
    "starter-pilot.md": "starter-pilot",
    "enterprise-adoption.md": "enterprise-adoption",
    "modernization.md": "legacy-modernization",
    "regulated-readiness.md": "regulated-readiness",
}
REFERENCE_DOCS = {
    "ai-dlc-adoption.md",
    "reference-architecture.md",
    "security-and-responsibility.md",
    "statement-of-work-template.md",
}
REQUIRED_HEADINGS = {
    "Customer problem",
    "Entry criteria and prerequisites",
    "Activities",
    "Deliverables and traceability",
    "Responsibilities",
    "Baseline and success metrics",
    "Planning assumptions",
    "Exclusions",
    "Exit criteria and acceptance",
}
PROHIBITED_CLAIMS = {
    "aws sponsored",
    "aws-certified",
    "certified compliant",
    "ensures compliance",
    "guaranteed productivity",
    "guaranteed cost savings",
}


def document(name: str) -> tuple[dict, str]:
    text = (COMMERCIAL / name).read_text(encoding="utf-8")
    marker, front, body = text.split("---", 2)
    assert not marker.strip()
    return yaml.safe_load(front), body


def manifest_assets() -> dict[str, set[str]]:
    manifest = yaml.safe_load((ROOT / "src" / "agora_ai_sdlc" / "flavor" / "flavor.yaml").read_text())
    return {
        "method_packs": set(manifest["method_packs"]),
        "profiles": set(manifest["profiles"]),
        "policies": set(manifest["policies"]),
    }


def test_package_set_and_implemented_asset_claims_match_release_manifest():
    assert {path.name for path in COMMERCIAL.glob("*.md")} == {
        *PACKAGES,
        *REFERENCE_DOCS,
        "README.md",
    }
    available = manifest_assets()
    for name, package_id in PACKAGES.items():
        front, _body = document(name)
        assert set(front) == {"package", "implemented_assets"} and front["package"] == package_id
        assert set(front["implemented_assets"]) == set(available)
        for kind, claimed in front["implemented_assets"].items():
            assert claimed and set(claimed) <= available[kind], (name, kind, claimed)


def test_every_package_has_contracting_sections_responsibilities_and_claim_labels():
    for name in PACKAGES:
        _front, body = document(name)
        headings = set(re.findall(r"^## (.+)$", body, re.MULTILINE))
        assert REQUIRED_HEADINGS <= headings, name
        assert "| Customer | Modern Ash |" in body
        assert "Implemented capability" in body and "Consulting work" in body
        assert "**Goal" in body and "not a schedule commitment" in body
        deliverables = body.split("## Deliverables and traceability", 1)[1].split("\n## ", 1)[0]
        rows = [line for line in deliverables.splitlines() if line.startswith("|")][2:]
        assert rows and all("Implemented capability" in row or "Consulting work" in row for row in rows)


def test_commercial_copy_has_no_unsupported_guarantee_endorsement_or_price():
    copy = "\n".join(path.read_text(encoding="utf-8") for path in COMMERCIAL.glob("*.md")).casefold()
    assert not any(claim in copy for claim in PROHIBITED_CLAIMS)
    assert "not sponsored, endorsed, or certified by aws" in copy
    assert "apache license 2.0" in copy
    assert not re.search(r"(?:usd|us\$|\$)\s*\d|hourly rate|fixed price", copy)


def test_every_package_links_the_common_software_services_boundary():
    for name in PACKAGES:
        _front, body = document(name)
        assert "[package overview](README.md)" in body


def test_statement_of_work_template_covers_contracting_topics_without_prices_or_guarantees():
    text = (COMMERCIAL / "statement-of-work-template.md").read_text(encoding="utf-8")
    headings = set(re.findall(r"^## \d+\. (.+)$", text, re.MULTILINE))
    assert {
        "Parties and documents",
        "Objective and scope",
        "Deliverables",
        "Roles and responsibilities",
        "Baseline, success measures, and goals",
        "Schedule and assumptions",
        "Data handling and security",
        "Acceptance",
        "Change control",
        "Claims and endorsement",
        "Commercial terms",
    } <= headings
    assert "Implemented capability" in text and "Consulting work" in text
    assert "not a schedule commitment" in text and "[package overview]" not in text
    assert "[professional-services packages](README.md)" in text


def test_regulated_readiness_never_claims_certification_or_compliance():
    _front, body = document("regulated-readiness.md")
    lowered = body.casefold()
    assert "certification" in lowered and "not legal advice" in lowered
    assert "no output states that the software, the organization, or a deployment is certified or compliant" in lowered
    assert "[Regulated profile](../profiles/regulated.md)" in body
