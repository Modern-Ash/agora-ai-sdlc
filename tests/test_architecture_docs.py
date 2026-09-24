import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
REQUIRED_TERMS = {
    "AI-SDLC",
    "Actor",
    "Role",
    "Runtime",
    "Provider",
    "Model",
    "Swarm",
    "Unit of Work",
    "Bolt",
    "Gate",
    "Evidence",
    "Profile",
    "Studio",
    "Control Plane",
}
VENDOR_ATTRIBUTION_ALLOWED = {
    "AGENTS.md",
    "README.md",
    "CHANGELOG.md",
    "docs/decision-plane-laya.md",
    "docs/method/overview.md",
    "docs/method/agora-flow-wizard.md",
    "docs/method/ai-dlc-compatibility.md",
    "docs/method/lifecycle.md",
    "docs/product/positioning.md",
    "docs/reference/aws-ai-dlc-mapping.md",
    "docs/reference/aws-ai-dlc-fidelity-plan.md",
    "docs/commercial",
    ".agora",
}


def defined_terms() -> list[str]:
    text = (DOCS / "terminology.md").read_text(encoding="utf-8")
    return re.findall(r"^\| ([^|]+?) \|", text, re.MULTILINE)[1:]


def test_terminology_defines_required_concepts_once():
    terms = defined_terms()
    assert REQUIRED_TERMS <= set(terms)
    assert len(terms) == len({t.casefold() for t in terms})


def test_adrs_are_accepted_indexed_and_structured():
    adrs = sorted((DOCS / "decisions").glob("ADR-0*.md"))
    assert {a.name for a in adrs} >= {
        "ADR-0001-separate-flavor-repository.md",
        "ADR-0002-no-embedded-llm-sdk.md",
        "ADR-0003-provider-neutral-naming.md",
    }
    index = (DOCS / "decisions" / "README.md").read_text(encoding="utf-8")
    for adr in adrs:
        text = adr.read_text(encoding="utf-8")
        assert adr.name in index
        assert "- Status: accepted" in text
        for heading in ("Context", "Decision", "Alternatives considered", "Consequences"):
            assert f"## {heading}" in text


def test_vendor_dlc_name_only_in_attribution_files():
    offenders = []
    for path in [*ROOT.rglob("*.md"), *ROOT.rglob("*.py")]:
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("dist/", ".venv/", "tests/")) or any(rel.startswith(a) for a in VENDOR_ATTRIBUTION_ALLOWED):
            continue
        if re.search(r"\bAI-DLC\b", path.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert not offenders, offenders


def test_aws_is_inspiration_not_dependency():
    text = (DOCS / "reference" / "aws-ai-dlc-mapping.md").read_text(encoding="utf-8")
    assert "methodological inspiration, not a runtime dependency or endorsement" in text
    positioning = (DOCS / "product" / "positioning.md").read_text(encoding="utf-8")
    assert "not affiliated with or endorsed by AWS" in positioning
    vision = (DOCS / "product" / "vision.md").read_text(encoding="utf-8")
    assert "Markdown and Git remain the project source of truth" in vision


def test_architecture_states_ownership_layers_and_source_of_truth():
    arch = (DOCS / "architecture.md").read_text(encoding="utf-8")
    for layer in ("Core", "Flavor", "Studio", "Runtimes"):
        assert f"**{layer}**" in arch
    assert "Markdown and Git remain the project source of truth" in arch
    assert "No LLM SDK" in arch


def test_alignment_tables_use_a_closed_status_vocabulary_and_cite_public_sources():
    text = (DOCS / "reference" / "aws-ai-dlc-mapping.md").read_text(encoding="utf-8")
    allowed = {"aligned", "partial", "gap", "deliberate difference"}
    rows = [line for line in text.splitlines() if line.startswith("| ") and "---" not in line]
    statuses = {cell.strip() for row in rows for cell in row.split("|")[1:-1] if cell.strip() in allowed}
    assert statuses == allowed
    assert "aws.amazon.com/blogs/devops/ai-driven-development-life-cycle" in text
    assert "aidlc.pdf" in text
    assert "not affiliated with AWS" in text and "no text or prompts" in text.lower()
