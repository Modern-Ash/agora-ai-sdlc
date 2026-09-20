import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
MARKETPLACE = ROOT / "docs" / "commercial" / "marketplace"
EXPECTED = {
    "README.md",
    "listing.md",
    "claim-substantiation.md",
    "private-offer-inputs.md",
    "review-checklist.md",
}


def read(name: str) -> str:
    return (MARKETPLACE / name).read_text(encoding="utf-8")


def body_with_front_matter(name: str) -> tuple[dict, str]:
    marker, front, body = read(name).split("---", 2)
    assert not marker.strip()
    return yaml.safe_load(front), body


def test_listing_inventory_metadata_and_required_fields():
    assert {path.name for path in MARKETPLACE.glob("*.md")} == EXPECTED
    front, listing = body_with_front_matter("listing.md")
    assert front == {
        "status": "draft-not-submitted",
        "product_type": "professional-services",
        "submission_authorized": False,
        "claim_registry": "claim-substantiation.md",
    }
    required = {
        "Product title",
        "Short description",
        "Long description",
        "Highlights",
        "Product classification",
        "Delivery method",
        "Service dimensions",
        "Support information",
        "Additional resources",
        "Private-offer preparation",
    }
    assert required <= set(re.findall(r"^## (.+)$", listing, re.MULTILINE))


def test_listing_is_professional_services_private_offer_and_not_saas():
    _front, listing = body_with_front_matter("listing.md")
    lower = listing.casefold()
    assert "scoped professional services engagement purchased through an aws marketplace private offer" in lower
    assert "this listing is for professional services, not saas" in lower
    assert "apache license 2.0" in lower
    assert "customer-controlled repositories and environments" in lower
    assert "agora does not require aws" in lower
    assert "not aws-sponsored or aws-certified" in lower
    assert "engagement support, not 24x7 managed operations" in lower


def test_every_marketing_claim_has_exactly_one_substantiation_row():
    _front, listing = body_with_front_matter("listing.md")
    used = set(re.findall(r"\[(C\d{2})\]", listing))
    register = read("claim-substantiation.md")
    registered = re.findall(r"^\| (C\d{2}) \|", register, re.MULTILINE)
    assert used == set(registered)
    assert len(registered) == len(set(registered))
    assert used == {f"C{number:02d}" for number in range(1, 10)}
    for row in (line for line in register.splitlines() if re.match(r"^\| C\d{2} \|", line)):
        assert row.count("|") == 6
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert len(cells) == 5 and all(cells)
        assert "](" in cells[3]
        assert len(cells[4]) >= 40


def test_dimensions_match_packages_and_contain_no_prices():
    _front, listing = body_with_front_matter("listing.md")
    section = listing.split("## Service dimensions", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")][2:]
    names = {row.split("|")[1].strip() for row in rows}
    assert names == {"AI-SDLC Assessment", "Starter Pilot", "Enterprise Adoption", "Legacy Modernization"}

    all_copy = "\n".join(read(name) for name in EXPECTED)
    assert not re.search(r"(?:usd|us\$|\$|€|£)\s*\d|\b\d+(?:\.\d+)?\s*(?:usd|eur|gbp)\b", all_copy, re.IGNORECASE)
    assert not re.search(r"\b\d{12}\b", all_copy)
    assert not re.search(r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", all_copy)


def test_submission_inputs_are_placeholders_and_human_gate_stays_blocked():
    _front, listing = body_with_front_matter("listing.md")
    for placeholder in (
        "[RELATED_PRODUCT_REQUIRED]",
        "[SELLER_ASSIGNED_SKU]",
        "[PUBLIC_LOGO_URL]",
        "[PUBLIC_SUPPORT_CONTACT]",
    ):
        assert f"`{placeholder}`" in listing

    review = read("review-checklist.md")
    assert "**Submission status: BLOCKED**" in review
    assert "- [x]" not in review.casefold()
    assert review.count("- [ ]") >= 20
    for owner in ("Marketplace operations", "Editorial and claim review", "Legal, privacy, and security review"):
        assert f"## {owner}" in review


def test_private_offer_keeps_sensitive_values_outside_repository():
    offer = read("private-offer-inputs.md").casefold()
    for required in (
        "buyer aws account identifiers",
        "pricing dimension",
        "payment schedule",
        "statement of work",
        "acceptance owners",
        "support window",
        "related aws service or public marketplace product",
    ):
        assert required in offer
    assert "do not commit these values or documents here" in offer
    assert "marketplace submission and offer creation remain separate business actions" in offer


def test_no_unsupported_claims_and_all_local_links_resolve():
    all_copy = "\n".join(read(name) for name in EXPECTED)
    prohibited = {
        "aws sponsored",
        "aws certified",
        "aws partner",
        "guaranteed productivity",
        "guaranteed savings",
        "certified compliant",
        "hosted control plane is available",
    }
    assert not any(claim in all_copy.casefold() for claim in prohibited)

    for name in EXPECTED:
        document = MARKETPLACE / name
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", read(name)):
            if "://" not in target:
                assert (document.parent / target).resolve().exists(), (name, target)
