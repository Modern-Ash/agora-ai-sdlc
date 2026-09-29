from pathlib import Path

import pytest

from agora_ai_sdlc.context_manifest import ContextOverflowError, build_context_manifest
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_context import ExecutionContextSelection


def bundle() -> ExecutionBundle:
    return ExecutionBundle(
        schema="s",
        swarm="delivery",
        work="issue-298",
        stage="construction",
        next_action="implement",
        branch="ai-sdlc/issue-298",
        base_branch="main",
        head="abc",
        objective="bounded context",
        acceptance_criteria=("must work",),
        changed_paths=("src/a.py",),
        dirty_paths=(),
        related_paths=("src/a.py", "docs/extra.md"),
        languages=("python",),
        build_systems=("pytest",),
        verification_commands=("pytest",),
        risks=("security-sensitive",),
        governance={"human_approval_required": False, "missing_evidence": ("tests",)},
        deterministic_inception_path=None,
    )


def selection() -> ExecutionContextSelection:
    return ExecutionContextSelection(
        candidate_paths=("src/a.py", "docs/extra.md"),
        selected_paths=("src/a.py",),
        protected_paths=("src/a.py",),
        escalated_paths=(),
        classifications={"src/a.py": "required", "docs/extra.md": "irrelevant"},
        confidences={"src/a.py": 1.0, "docs/extra.md": 0.99},
        candidate_tokens=100,
        selected_tokens=60,
        latency_ms=1.0,
    )


def test_manifest_keeps_governance_mandatory_and_optional_provenance(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('safe')\n", encoding="utf-8")
    (tmp_path / "docs" / "extra.md").write_text("optional\n", encoding="utf-8")

    manifest = build_context_manifest(tmp_path, bundle(), selection(), runtime_limit_tokens=10000)

    assert {item.id for item in manifest.mandatory} >= {
        "work-identity",
        "acceptance-criteria",
        "governance",
        "risk-policy",
        "verification",
    }
    assert manifest.selected_optional[0].provenance == "repository:src/a.py"
    assert manifest.available_optional[0].id == "docs/extra.md"
    assert manifest.available_optional[0].provenance == "repository:docs/extra.md"
    assert manifest.overflow is False


def test_mandatory_context_overflow_is_explicit(tmp_path: Path):
    with pytest.raises(ContextOverflowError) as error:
        build_context_manifest(tmp_path, bundle(), selection(), runtime_limit_tokens=1)

    assert error.value.required_tokens > error.value.limit_tokens


def test_optional_overflow_is_reported_not_silently_pruned(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 'large'\n" * 1000, encoding="utf-8")

    baseline = build_context_manifest(tmp_path, bundle(), selection())
    mandatory = sum(item.estimated_tokens for item in baseline.mandatory)
    manifest = build_context_manifest(
        tmp_path,
        bundle(),
        selection(),
        runtime_limit_tokens=mandatory + 1,
    )

    assert manifest.overflow is True
    assert manifest.selected_optional


def test_sensitive_optional_file_content_is_never_materialized(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=super-secret-value\n", encoding="utf-8")
    sensitive_selection = ExecutionContextSelection(
        candidate_paths=("src/a.py", ".env"),
        selected_paths=("src/a.py", ".env"),
        protected_paths=("src/a.py",),
        escalated_paths=(),
        classifications={"src/a.py": "required", ".env": "useful"},
        confidences={"src/a.py": 1.0, ".env": 0.99},
        candidate_tokens=100,
        selected_tokens=80,
        latency_ms=1.0,
    )

    manifest = build_context_manifest(tmp_path, bundle(), sensitive_selection)
    env_item = next(item for item in manifest.selected_optional if item.id == ".env")

    assert env_item.provenance == "repository:.env"
    assert "super-secret-value" not in env_item.digest
