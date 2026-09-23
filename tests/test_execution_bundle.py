import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc import execution_bundle
from agora_ai_sdlc.execution_bundle import build_execution_bundle


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "bundle@example.test")
    _git(root, "config", "user.name", "Bundle Test")

    source = root / "src" / "interpreter.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "class Interpreter:\n    execution_budget = 10\n",
        encoding="utf-8",
    )
    test = root / "tests" / "test_interpreter.py"
    test.parent.mkdir(parents=True)
    test.write_text("def test_interpreter(): pass\n", encoding="utf-8")
    (root / "src" / "unrelated.py").write_text("payment invoice customer ledger\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")

    _git(root, "switch", "-c", "ai-sdlc/issue-14")
    source.write_text(
        "class Interpreter:\n    execution_budget = 20\n    stop_supported = True\n",
        encoding="utf-8",
    )
    _git(root, "add", "src/interpreter.py")
    _git(root, "commit", "-m", "implement budget")

    (root / "README.md").write_text("# dirty\n", encoding="utf-8")


def _inception(root: Path) -> None:
    path = root / ".agora" / "ai-sdlc" / "handoffs" / "issue-14" / "DETERMINISTIC_INCEPTION.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "## Intent interpretation\n\n"
        "Execute learner programs with an interpreter and explicit execution budget.\n\n"
        "## Acceptance criteria trace\n\n"
        "- AC-001: execution budget path -> plan step implement-01 -> bolt verify-01\n"
        "- AC-002: stop outcome explicit -> plan step implement-02 -> bolt verify-02\n",
        encoding="utf-8",
    )


def _status():
    return SimpleNamespace(
        swarm="delivery",
        work="issue-14",
        state="construction",
        base_branch="main",
        work_branch="ai-sdlc/issue-14",
        current_branch="ai-sdlc/issue-14",
        missing_artifacts=(),
        missing_evidence=("verification",),
        missing_approvals=(),
        unsatisfied_criteria=("AC-002",),
        git_issues=(),
        clarification_issues=(),
        ready_to_transition=False,
        agent_context=lambda: {
            "schema": "agora-ai-sdlc/agent-context/v1",
            "next_action": "resolve-governance-obligations",
        },
    )


def test_execution_bundle_collects_git_repo_and_inception_facts(monkeypatch, tmp_path: Path):
    _repo(tmp_path)
    _inception(tmp_path)
    monkeypatch.setattr(execution_bundle, "inspect_iteration", lambda *args, **kwargs: _status())

    bundle = build_execution_bundle(
        tmp_path,
        swarm="delivery",
        work="issue-14",
    )

    assert bundle.schema == "agora-ai-sdlc/execution-bundle/v1"
    assert bundle.stage == "construction"
    assert bundle.base_branch == "main"
    assert bundle.branch == "ai-sdlc/issue-14"
    assert bundle.head == _git(tmp_path, "rev-parse", "HEAD")
    assert bundle.changed_paths == ("src/interpreter.py",)
    assert "README.md" in bundle.dirty_paths
    assert "src/interpreter.py" in bundle.related_paths
    assert bundle.languages == ("Python",)
    assert bundle.build_systems == ("Python",)
    assert bundle.verification_commands == ("pytest",)
    assert bundle.acceptance_criteria == (
        "execution budget path",
        "stop outcome explicit",
    )
    assert "source-change-without-test-change" in bundle.risks
    assert "working-tree-dirty" in bundle.risks
    assert bundle.governance["missing_evidence"] == ("verification",)
    assert bundle.governance["unsatisfied_criteria"] == ("AC-002",)

    assert bundle.json_path is not None
    assert bundle.markdown_path is not None
    payload = json.loads(Path(bundle.json_path).read_text(encoding="utf-8"))
    assert payload["head"] == bundle.head
    assert payload["related_paths"][0] == "src/interpreter.py"
    rendered = Path(bundle.markdown_path).read_text(encoding="utf-8")
    assert "Deterministic execution bundle" in rendered
    assert "source-change-without-test-change" in rendered


def test_execution_bundle_no_write_is_read_only_for_bundle_paths(monkeypatch, tmp_path: Path):
    _repo(tmp_path)
    _inception(tmp_path)
    monkeypatch.setattr(execution_bundle, "inspect_iteration", lambda *args, **kwargs: _status())

    bundle = build_execution_bundle(
        tmp_path,
        swarm="delivery",
        work="issue-14",
        persist=False,
    )

    assert bundle.json_path is None
    assert bundle.markdown_path is None
    assert not (tmp_path / ".agora" / "ai-sdlc" / "bundles").exists()


def test_related_files_use_bounded_issue_terms_not_full_repo_replay(monkeypatch, tmp_path: Path):
    _repo(tmp_path)
    _inception(tmp_path)
    monkeypatch.setattr(execution_bundle, "inspect_iteration", lambda *args, **kwargs: _status())

    bundle = build_execution_bundle(tmp_path, work="issue-14", persist=False)

    assert "src/interpreter.py" in bundle.related_paths
    assert "src/unrelated.py" not in bundle.related_paths
