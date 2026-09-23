from pathlib import Path

from agora_ai_sdlc.inception_validation import validate_inception_output


def handoff(tmp_path: Path) -> Path:
    path = tmp_path / "INCEPTION_HANDOFF.md"
    path.write_text(
        "# Inception\n\n"
        "## Objective\n\n"
        "Implement deterministic canonical program interpreter\n\n"
        "## Required Inception output contract\n",
        encoding="utf-8",
    )
    return path


def valid_output() -> str:
    return (
        "## Intent interpretation\n\n"
        "Implement the deterministic canonical program interpreter without generated-code execution.\n\n"
        "## Material clarifications\n\n"
        "No unresolved material clarification is required from the source issue.\n\n"
        "## Level 1 Plan\n\n"
        "Define interpreter semantics, deterministic transitions, execution budget, stop handling, and tests.\n\n"
        "## Proposed Units\n\n"
        "One cohesive interpreter unit plus its test coverage.\n\n"
        "## Suggested Bolts\n\n"
        "A single implementation bolt is sufficient after approval.\n\n"
        "## Acceptance criteria trace\n\n"
        "Trace interpreter operations and deterministic behavior to issue #14 acceptance criteria.\n\n"
        "## Risks, constraints and dependencies\n\n"
        "No eval, no generated-code execution, no UI or AI dependency; depends on the canonical program model.\n\n"
        "## Source facts and proposed decisions\n\n"
        "Source fact: deterministic interpreter. AI proposal: keep interpreter execution isolated from UI.\n\n"
        "## Files created or modified\n\n"
        "No product files modified during Inception.\n\n"
        "## Human decision required\n\n"
        "Approve or adjust this proposal before Construction.\n"
    )


def test_valid_inception_output_passes(tmp_path: Path):
    result = validate_inception_output(valid_output(), handoff(tmp_path))

    assert result.valid is True
    assert result.violations == ()


def test_unrelated_nonempty_output_is_rejected(tmp_path: Path):
    output = (
        "## Inception Proposal\n\n"
        "I will create a simple Flask API call handler.\n\n"
        "```python\n"
        "class Client:\n"
        "    pass\n"
        "```\n\n"
        "## Human decision required\n\n"
        "Approve or modify.\n"
    )

    result = validate_inception_output(output, handoff(tmp_path))

    assert result.valid is False
    assert "missing section: Intent interpretation" in result.violations
    assert any("not grounded in the handoff objective" in item for item in result.violations)


def test_structured_but_unrelated_output_is_rejected_by_objective_grounding(tmp_path: Path):
    output = valid_output()
    replacements = {
        "Implement the deterministic canonical program interpreter without generated-code execution.":
            "Create a Flask API client for HTTP requests.",
        "Trace interpreter operations and deterministic behavior to issue #14 acceptance criteria.":
            "Trace HTTP status handling to API requirements.",
        "Source fact: deterministic interpreter. AI proposal: keep interpreter execution isolated from UI.":
            "Source fact: API endpoint. AI proposal: use Flask.",
        "Define interpreter semantics, deterministic transitions, execution budget, stop handling, and tests.":
            "Define API client calls and logging.",
        "One cohesive interpreter unit plus its test coverage.":
            "One API client unit plus tests.",
        "No eval, no generated-code execution, no UI or AI dependency; depends on the canonical program model.":
            "Depends on Flask and HTTP connectivity.",
    }
    for source, target in replacements.items():
        output = output.replace(source, target)

    result = validate_inception_output(output, handoff(tmp_path))

    assert result.valid is False
    assert any("not grounded in the handoff objective" in item for item in result.violations)
