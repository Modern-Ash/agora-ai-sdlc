from pathlib import Path

from agora_ai_sdlc.deterministic_inception import (
    build_deterministic_inception,
    inspect_repository,
    normalize_issue,
)


def explicit_issue():
    return {
        "number": 14,
        "title": "Implement deterministic canonical program interpreter",
        "body": (
            "## Objective\n"
            "Execute learner programs deterministically without generated-code execution.\n\n"
            "## Semantics\n"
            "- onStart\n"
            "- move\n"
            "- turn\n"
            "- repeat\n"
            "- if\n"
            "- touchingGoal\n\n"
            "## Requirements\n"
            "- deterministic state transitions\n"
            "- explicit execution budget\n"
            "- stop support\n"
            "- no UI dependency\n"
            "- no AI dependency\n"
            "- no eval or arbitrary JavaScript execution\n\n"
            "## Dependencies\n"
            "- Program model\n"
            "- validation\n\n"
            "## Acceptance\n"
            "- tests for each operation\n"
            "- nested repeat/if\n"
            "- execution budget path\n"
            "- deterministic repeated run\n"
            "- stop outcome explicit\n"
            "- same canonical model drives runtime and visible generated code\n"
        ),
    }


def test_explicit_issue_requires_no_llm_and_preserves_contract(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    source = tmp_path / "src" / "interpreter.py"
    source.parent.mkdir(parents=True)
    source.write_text("def run(): pass\n", encoding="utf-8")
    test = tmp_path / "tests" / "test_interpreter.py"
    test.parent.mkdir(parents=True)
    test.write_text("def test_run(): pass\n", encoding="utf-8")

    result = build_deterministic_inception(
        tmp_path,
        explicit_issue(),
        intent_id="issue-14",
        work_id="issue-14",
        pathway="new-product",
    )

    assert result.requires_llm is False
    assert result.semantic_gaps == ()
    assert result.repository.languages == ("Python",)
    assert "pytest" in result.repository.test_commands
    for heading in (
        "## Intent interpretation",
        "## Material clarifications",
        "## Level 1 Plan",
        "## Proposed Units",
        "## Suggested Bolts",
        "## Acceptance criteria trace",
        "## Risks, constraints and dependencies",
        "## Source facts and proposed decisions",
        "## Files created or modified",
        "## Human decision required",
    ):
        assert heading in result.output
    assert "AC-001" in result.output
    assert Path(result.path).is_file()


def test_sparse_issue_keeps_semantic_gap_for_llm():
    facts = normalize_issue(
        {
            "title": "Improve the interpreter",
            "body": "Please make it better.",
        }
    )

    assert facts.objective == "Improve the interpreter"
    assert facts.semantic_gaps == ("acceptance criteria or requirements are not explicit",)


def test_constraints_are_derived_from_explicit_negative_requirements():
    facts = normalize_issue(explicit_issue())

    assert "no UI dependency" in facts.constraints
    assert "no AI dependency" in facts.constraints
    assert "no eval or arbitrary JavaScript execution" in facts.constraints


def test_repository_inspection_detects_common_js_and_java_test_names(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"vitest"}}\n', encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    source = tmp_path / "src" / "interpreter.ts"
    source.parent.mkdir(parents=True)
    source.write_text("export const run = () => true;\n", encoding="utf-8")
    spec = tmp_path / "src" / "interpreter.spec.ts"
    spec.write_text("test('run', () => {});\n", encoding="utf-8")
    java_test = tmp_path / "java" / "InterpreterTest.java"
    java_test.parent.mkdir(parents=True)
    java_test.write_text("class InterpreterTest {}\n", encoding="utf-8")

    facts = inspect_repository(tmp_path)

    assert facts.test_files == 2
    assert "pnpm" in facts.build_systems
    assert facts.test_commands == ("pnpm test",)
    assert "npm test" not in facts.test_commands


def test_repository_inspection_is_bounded_and_skips_generated_trees(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    src = tmp_path / "src" / "main" / "java" / "Interpreter.java"
    src.parent.mkdir(parents=True)
    src.write_text("class Interpreter {}", encoding="utf-8")
    ignored = tmp_path / "target" / "Generated.java"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("class Generated {}", encoding="utf-8")

    facts = inspect_repository(tmp_path)

    assert facts.languages == ("Java",)
    assert facts.build_systems == ("Maven",)
    assert facts.test_commands == ("mvn test",)
