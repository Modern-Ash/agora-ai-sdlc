import subprocess
from pathlib import Path

import pytest
from agora.markdown import read_markdown
from agora.model import InitInput
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.start_preflight import (
    StartPreparationError,
    ensure_start_ready,
    isolate_dirty_work,
)


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
    _git(root, "config", "user.email", "agora@example.test")
    _git(root, "config", "user.name", "Agora Test")
    (root / "README.md").write_text("# demo\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "initial")


def _runtime(runtime_id: str = "opencode") -> RuntimeDiscovery:
    return RuntimeDiscovery(
        id=runtime_id,
        name={"opencode": "OpenCode", "codex": "Codex", "claude": "Claude Code"}.get(runtime_id, runtime_id),
        command=runtime_id,
        installed=True,
        executable=f"/bin/{runtime_id}",
        responsive=True,
        version="1.0",
        configured=False,
    )


def test_start_preflight_bootstraps_existing_repository_without_agora(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)

    result = ensure_start_ready(project, _runtime())

    assert result.root == project.resolve()
    assert "project.initialized" in result.actions
    assert "method.installed" in result.actions
    assert "skill.installed" in result.actions
    assert "github-adapter.installed" in result.actions
    assert "swarm.created" in result.actions

    project_doc = read_markdown(project / ".agora" / "project.md")
    assert project_doc.attributes["active-flavor"] == "ai-sdlc"
    assert project_doc.attributes["active-profile"] == "starter"

    workspace = AgoraWorkspace(cwd=project)
    swarm = workspace.show_swarm("delivery")
    assert swarm.method == "ai-sdlc"
    assert swarm.assignments["product-owner"] == "project:product-owner"
    assert swarm.assignments["developer"] == "project:ai-opencode"
    assert (project / ".agora" / "methods" / "ai-sdlc" / "METHOD.md").is_file()
    assert (project / ".agora" / "skills" / "agora-ai-sdlc-guided" / "SKILL.md").is_file()
    assert (project / ".agora" / "tools" / "github-issues" / "TOOL.md").is_file()


def test_start_preflight_layers_ai_sdlc_over_generic_core_project(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)

    workspace = AgoraWorkspace(cwd=project)
    workspace.initialize(
        InitInput(
            integration="codex",
            provider="openai",
            model="configured-by-codex",
            default_method="spec-driven",
        )
    )

    result = ensure_start_ready(project, _runtime())

    assert "project.flavor-selected" in result.actions
    doc = read_markdown(project / ".agora" / "project.md")
    assert doc.attributes["active-flavor"] == "ai-sdlc"
    assert doc.attributes["active-profile"] == "starter"
    assert doc.attributes["active-depth"]


def test_start_preflight_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)

    first = ensure_start_ready(project, _runtime())
    second = ensure_start_ready(project, _runtime())

    assert first.actions
    assert second.actions == ()


def test_start_preflight_repairs_formatter_wrapped_method_front_matter(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)
    ensure_start_ready(project, _runtime())

    method = project / ".agora" / "methods" / "ai-sdlc" / "METHOD.md"
    text = method.read_text(encoding="utf-8")
    text = text.replace(
        'criterion-stages: ["elaborated", "designed", "built", "verified", "deployed", "accepted"]',
        'criterion-stages:\n  ["elaborated", "designed", "built", "verified", "deployed", "accepted"]',
    )
    method.write_text(text, encoding="utf-8")

    result = ensure_start_ready(project, _runtime())

    assert any(action.startswith("state.front-matter-repaired:") for action in result.actions)
    assert "pack-lock.refreshed" in result.actions
    assert read_markdown(method).attributes["criterion-stages"] == [
        "elaborated",
        "designed",
        "built",
        "verified",
        "deployed",
        "accepted",
    ]


def test_start_preflight_repairs_formatter_wrapped_role_front_matter_without_changing_body(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)
    ensure_start_ready(project, _runtime())

    role = project / ".agora" / "methods" / "ai-sdlc" / "roles" / "product-owner.md"
    original = role.read_text(encoding="utf-8")
    marker = "allowed-actions: "
    line = next(line for line in original.splitlines() if line.startswith(marker))
    wrapped = original.replace(line, f"allowed-actions:\n  {line.removeprefix(marker)}")
    role.write_text(wrapped, encoding="utf-8")

    result = ensure_start_ready(project, _runtime())

    assert any(action.startswith("state.front-matter-repaired:") for action in result.actions)
    assert "pack-lock.refreshed" in result.actions
    repaired = role.read_text(encoding="utf-8")
    assert "allowed-actions: [" in repaired
    assert repaired.split("---", 2)[2].strip() == original.split("---", 2)[2].strip()


def test_start_preflight_refuses_to_overwrite_unknown_malformed_method_customization(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)
    ensure_start_ready(project, _runtime())

    method = project / ".agora" / "methods" / "ai-sdlc" / "METHOD.md"
    method.write_text(
        method.read_text(encoding="utf-8").replace(
            'criterion-stages: ["elaborated", "designed", "built", "verified", "deployed", "accepted"]',
            'criterion-stages: ["custom", }',
        )
        + "\nLocal governance customization.\n",
        encoding="utf-8",
    )

    with pytest.raises(StartPreparationError, match="local customizations"):
        ensure_start_ready(project, _runtime())


def test_start_preflight_restores_missing_guided_skill_resource(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)
    ensure_start_ready(project, _runtime())

    missing = project / ".agora" / "skills" / "agora-ai-sdlc-guided" / "references" / "construction.md"
    missing.unlink()

    result = ensure_start_ready(project, _runtime())

    assert "skill.installed" in result.actions
    assert missing.is_file()




def test_start_preflight_repairs_body_only_github_issue_operation(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)
    ensure_start_ready(project, _runtime())

    operation = project / ".agora" / "tools" / "github-issues" / "operations" / "view.md"
    original = operation.read_text(encoding="utf-8")
    body = original.split("---", 2)[2]
    operation.write_text(body.lstrip(), encoding="utf-8")

    result = ensure_start_ready(project, _runtime())

    assert "github-adapter.repaired" in result.actions
    assert "pack-lock.refreshed" in result.actions
    assert read_markdown(operation).attributes["id"] == "view"


def test_start_preflight_refuses_unknown_github_adapter_customization(tmp_path, monkeypatch):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)
    ensure_start_ready(project, _runtime())

    operation = project / ".agora" / "tools" / "github-issues" / "operations" / "view.md"
    operation.write_text("# custom local operation\n", encoding="utf-8")

    with pytest.raises(StartPreparationError, match="GitHub Issues adapter"):
        ensure_start_ready(project, _runtime())


def test_dirty_unrelated_branch_gets_isolated_worktree_without_stash_or_reset(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)
    _git(project, "switch", "-c", "feat/other-work")
    original = project / "README.md"
    original.write_text("# dirty work\n", encoding="utf-8")

    isolated, action = isolate_dirty_work(project, 14)

    assert action == "workspace.created"
    assert isolated != project
    assert _git(isolated, "branch", "--show-current") == "ai-sdlc/issue-14"
    assert _git(project, "branch", "--show-current") == "feat/other-work"
    assert original.read_text(encoding="utf-8") == "# dirty work\n"
    assert _git(project, "status", "--porcelain")


def test_dirty_issue_workspace_is_reused_on_second_start(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    _repo(project)
    _git(project, "switch", "-c", "feat/other-work")
    (project / "README.md").write_text("# dirty work\n", encoding="utf-8")

    first, first_action = isolate_dirty_work(project, 14)
    second, second_action = isolate_dirty_work(project, 14)

    assert first_action == "workspace.created"
    assert second_action == "workspace.reused"
    assert second == first


def test_non_git_directory_fails_with_actionable_message(tmp_path):
    with pytest.raises(StartPreparationError, match="not inside a Git work tree"):
        isolate_dirty_work(tmp_path, 14)
