import json
import re
from pathlib import Path

import pytest

from agora_ai_sdlc.artifacts import (
    PARENTS,
    PREFIX,
    TEMPLATE_FILES,
    ArtifactError,
    check_traceability,
    parse_artifact,
    parse_template,
    sections_of,
    split,
)  # fmt: skip

ROOT = Path(__file__).parent.parent
TEMPLATES = ROOT / "templates"
GATES = ROOT / "registry" / "methods" / "ai-sdlc" / "gates"
FIXTURES = Path(__file__).parent / "fixtures" / "trace"


def template_for(kind):
    return TEMPLATES / f"{TEMPLATE_FILES.get(kind, kind)}.md"


def gate_required_kinds():
    kinds = set()
    for gate in GATES.glob("*.md"):
        for line in gate.read_text().splitlines():
            if line.startswith("required-artifacts:"):
                kinds |= set(json.loads(line.split(":", 1)[1]))
    return kinds


def test_every_gate_required_artifact_has_a_template():
    kinds = gate_required_kinds()
    assert kinds  # guard against parsing regressions
    for kind in kinds:
        assert kind in PREFIX, kind
        assert template_for(kind).is_file(), kind
        assert parse_template(template_for(kind).read_text()).kind == kind


def test_all_required_templates_exist():
    wanted = {
        "readiness-assessment", "intent", "clarification", "unit-of-work", "requirements", "domain-model",
        "architecture", "threat-model", "test-strategy", "implementation-plan", "deployment-plan", "plan", "bolt-plan", "impact-analysis", "change-request", "change-plan", "configuration-delta", "static-system-model", "dynamic-system-model",
        "operational-readiness", "learning-record",
        "legacy-inventory", "dependency-map", "characterization", "target-architecture", "migration-plan",
        "migration-slice", "conversion-record", "equivalence-report", "cutover-plan", "stabilization-report",
    }  # fmt: skip
    for kind in wanted:
        assert parse_template(template_for(kind).read_text()).kind == kind


def test_prefixes_and_parent_rules_cover_every_kind():
    assert set(PREFIX) == set(PARENTS)
    assert len(set(PREFIX.values())) == len(PREFIX)


@pytest.mark.parametrize("path", sorted(TEMPLATES.glob("*.md")))
def test_templates_are_valid_markdown_with_front_matter(path):
    if path.name == "README.md":
        pytest.skip("index")
    text = path.read_text()
    front, body = split(text)
    assert front["schema"] == "agora-ai-sdlc/artifact/v1"
    assert set(front["required-sections"]) <= set(sections_of(body))
    assert not re.search(r"<\|[a-z_]+\|>|\{\{|\bAssistant:|\[INST\]", text)  # no provider prompt syntax


def test_golden_chain_parses_and_traces():
    artifacts = [parse_artifact(p.read_text()) for p in sorted(FIXTURES.glob("*.md"))]
    check_traceability(artifacts)
    assert {a.kind for a in artifacts} >= {"intent", "requirements", "test-strategy", "deployment-plan"}


def load(name):
    return parse_artifact((FIXTURES / name).read_text())


def chain(**drop):
    return [load(p.name) for p in sorted(FIXTURES.glob("*.md")) if p.name not in drop.get("drop", ())]


def code_of(fn):
    with pytest.raises(ArtifactError) as exc:
        fn()
    return exc.value.code


def test_missing_required_section():
    text = (FIXTURES / "intent.md").read_text().replace("## Section", "## Other")
    assert code_of(lambda: parse_artifact(text)) == "artifact.missing_section"


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        ('schema: "agora-ai-sdlc/artifact/v1"', 'schema: "x/v2"', "artifact.schema"),
        ('kind: "intent"', 'kind: "nope"', "artifact.kind"),
        ("version: 1", "version: 2", "artifact.version"),
        ('id: "INT-001"', 'id: "REQ-001"', "artifact.id"),
        ('id: "INT-001"', 'id: "int-1"', "artifact.id"),
    ],
)
def test_front_matter_rules(old, new, code):
    text = (FIXTURES / "intent.md").read_text().replace(old, new, 1)
    assert code_of(lambda: parse_artifact(text)) == code


def test_no_front_matter():
    assert code_of(lambda: parse_artifact("# nothing")) == "artifact.front_matter"


def test_dangling_reference():
    items = chain()
    items = [a for a in items if a.kind != "unit-of-work"]
    assert code_of(lambda: check_traceability(items)) == "trace.dangling"


def test_missing_parent_and_wrong_parent_kind():
    text = (FIXTURES / "unit.md").read_text().replace('traces-to: ["INT-001"]', "traces-to: []")
    items = [a for a in chain() if a.kind != "unit-of-work"] + [parse_artifact(text)]
    assert code_of(lambda: check_traceability(items)) == "trace.missing_parent"
    text = (FIXTURES / "dep.md").read_text().replace('"IMP-001"', '"INT-001"')
    items = [a for a in chain() if a.kind != "deployment-plan"] + [parse_artifact(text)]
    assert code_of(lambda: check_traceability(items)) == "trace.parent_kind"


def test_duplicate_id():
    assert code_of(lambda: check_traceability(chain() + [load("intent.md")])) == "trace.duplicate_id"


def test_uncovered_and_unknown_criteria():
    text = (FIXTURES / "test.md").read_text()
    uncovered = text.replace('covers-criteria: ["value"]', "covers-criteria: []")
    items = [a for a in chain() if a.kind != "test-strategy"] + [parse_artifact(uncovered)]
    assert code_of(lambda: check_traceability(items)) == "trace.uncovered_criterion"
    unknown = text.replace('covers-criteria: ["value"]', 'covers-criteria: ["value", "ghost"]')
    items = [a for a in chain() if a.kind != "test-strategy"] + [parse_artifact(unknown)]
    assert code_of(lambda: check_traceability(items)) == "trace.unknown_criterion"
