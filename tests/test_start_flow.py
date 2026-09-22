import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from agora.model import CreateWorkInput

from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.start_flow import (
    StartFlowError,
    infer_project,
    prepare_start,
    render_start,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "agorix@example.test")
    _git(root, "config", "user.name", "Agorix Test")
    (root / "README.md").write_text("# agorix\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "initial")


def runtime(runtime_id="codex", *, responsive=True, configured=True):
    return RuntimeDiscovery(
        id=runtime_id,
        name={"codex": "Codex", "claude": "Claude Code"}.get(runtime_id, runtime_id),
        command=runtime_id,
        installed=True,
        executable=f"/bin/{runtime_id}",
        responsive=responsive,
        version="1.0",
        configured=configured,
    )


class FakeWorkspace:
    def __init__(self, cwd: Path):
        self.cwd = cwd
        self.invocations = []
        self.installed_adapters = []
        self.installed_methods = []
        self.created_work_inputs = []
        self._works = []
        self._has_run = False
        self._intent = None

    def list_work(self, swarm_id=None):
        return list(self._works)

    def create_work(self, data):
        self.created_work_inputs.append(data)
        work = SimpleNamespace(
            id=data.id,
            swarm_id=data.swarm_id,
            title=data.title,
            path=str(self.cwd / ".agora" / "swarms" / data.swarm_id / "work" / data.id / "WORK.md"),
            base_branch=getattr(data, "base_branch", None),
            branch=getattr(data, "branch", None),
        )
        self._works.append(work)
        return work

    def show_tool_run(self, run_id):
        if not self._has_run:
            raise FileNotFoundError(run_id)
        payload = {
            "number": 11,
            "title": "Initialize TypeScript pnpm monorepo and engineering toolchain",
            "body": "## Parent\n#2\n\n## Objective\nEstablish the shared engineering foundation for Agorix.",
            "url": "https://github.com/Modern-Ash/agorix/issues/11",
        }
        return SimpleNamespace(
            result=SimpleNamespace(
                status="completed",
                stdout=json.dumps(payload),
                stderr="",
            )
        )

    def install_tool_adapter(self, data):
        self.installed_adapters.append(data)
        tool = self.cwd / ".agora" / "tools" / data.adapter_id / "TOOL.md"
        tool.parent.mkdir(parents=True, exist_ok=True)
        tool.write_text("adapter", encoding="utf-8")
        return SimpleNamespace(id=data.adapter_id)

    def install_method(self, data):
        self.installed_methods.append(data)
        role = self.cwd / ".agora" / "methods" / "ai-sdlc" / "roles" / "product-owner.md"
        role.parent.mkdir(parents=True, exist_ok=True)
        role.write_text(
            'allowed-tool-capabilities: ["repository.read", "repository.governance.read", '
            '"docs.read", "docs.write", "issue.read"]\n',
            encoding="utf-8",
        )
        return SimpleNamespace(id="ai-sdlc")

    def invoke_tool(self, data):
        self.invocations.append(data)
        self._has_run = True
        return SimpleNamespace(id=data.id)

    def list_intents(self):
        return [] if self._intent is None else [self._intent]

    def create_intent(self, data):
        self.last_intent_input = data
        self._intent = SimpleNamespace(
            id=data.id,
            path=str(self.cwd / ".agora" / "intents" / data.id / "INTENT.md"),
            source=data.source,
            status="draft",
        )
        return self._intent


def test_infer_project_from_https_origin(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "agora_ai_sdlc.start_flow._run_git",
        lambda root, *args: "https://github.com/Modern-Ash/agorix.git",
    )
    assert infer_project(tmp_path) == "Modern-Ash/agorix"


def test_prepare_start_reads_issue_through_governed_tool_and_creates_draft_intent(tmp_path):
    workspace = FakeWorkspace(tmp_path)

    result = prepare_start(
        tmp_path,
        issue=11,
        project="Modern-Ash/agorix",
        agent="codex",
        workspace_factory=lambda cwd: workspace,
        runtime_discovery=lambda root: (runtime(),),
    )

    assert result.intent_id == "issue-11"
    assert result.work_id == "issue-11"
    supports_work_branch = "branch" in getattr(CreateWorkInput, "__dataclass_fields__", {})
    assert result.branch == ("ai-sdlc/issue-11" if supports_work_branch else None)
    assert result.pathway == "new-product"
    assert result.status == "human-review-required"
    assert result.handoff_path.endswith(".agora/ai-sdlc/handoffs/issue-11/INCEPTION_HANDOFF.md")
    assert len(workspace.created_work_inputs) == 1
    if supports_work_branch:
        assert workspace.created_work_inputs[0].create_branch is True
        assert workspace.created_work_inputs[0].branch == "ai-sdlc/issue-11"
    assert [item.adapter_id for item in workspace.installed_adapters] == ["github-issues"]
    assert len(workspace.invocations) == 1
    invocation = workspace.invocations[0]
    assert invocation.tool_id == "github-issues"
    assert invocation.operation_id == "view"
    assert invocation.actor_id == "product-owner"
    assert invocation.swarm_id == "delivery"
    assert invocation.inputs == {"issue": "https://github.com/Modern-Ash/agorix/issues/11"}
    assert invocation.launch is True
    assert workspace._intent.status == "draft"
    assert workspace._intent.source.endswith("/issues/11")
    assert workspace.last_intent_input.outcome == (
        "Deliver the outcome described by GitHub issue #11: "
        "Initialize TypeScript pnpm monorepo and engineering toolchain"
    )
    assert "## Parent" not in workspace.last_intent_input.outcome

    output = render_start(result)
    assert "Candidate Intent: issue-11 (draft)" in output
    assert "Propose the Level 1 Plan" in output
    assert "Propose cohesive Units and suggested Bolts" in output
    assert "No Intent acceptance" in output
    assert "Portable Inception handoff" in output
    assert "No ad hoc methodology prompt is required." in output
    assert "human-review-required" in output

    spanish = render_start(result, lang="es")
    assert "Agora AI-SDLC | Inicio" in spanish
    assert "Intent candidato: issue-11 (borrador)" in spanish
    assert "Estado: human-review-required" in spanish

    handoff = Path(result.handoff_path).read_text(encoding="utf-8")
    assert 'schema: "agora-ai-sdlc/inception-handoff/v1"' in handoff
    assert "Level 1 Plan" in handoff
    assert 'work: "issue-11"' in handoff
    assert f'branch: "{result.branch or ""}"' in handoff
    assert 'pathway: "new-product"' in handoff
    assert "Cohesive Units" in handoff
    assert "Suggested Bolts" in handoff
    assert "Do not enter Construction." in handoff
    assert "Do not fabricate or infer human approval." in handoff


def test_prepare_start_repairs_legacy_product_owner_issue_read(tmp_path):
    workspace = FakeWorkspace(tmp_path)
    adapter = tmp_path / ".agora" / "tools" / "github-issues" / "TOOL.md"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("adapter", encoding="utf-8")
    role = tmp_path / ".agora" / "methods" / "ai-sdlc" / "roles" / "product-owner.md"
    role.parent.mkdir(parents=True)
    role.write_text(
        'allowed-tool-capabilities: ["repository.read", "repository.governance.read", "docs.read", "docs.write"]\n',
        encoding="utf-8",
    )

    result = prepare_start(
        tmp_path,
        issue=11,
        project="Modern-Ash/agorix",
        workspace_factory=lambda cwd: workspace,
        runtime_discovery=lambda root: (runtime(),),
    )

    assert result.intent_id == "issue-11"
    assert len(workspace.installed_methods) == 1
    repair = workspace.installed_methods[0]
    assert repair.scope == "project"
    assert repair.force is True
    assert '"issue.read"' in role.read_text(encoding="utf-8")


def test_prepare_start_rejects_unavailable_requested_runtime(tmp_path):
    with pytest.raises(StartFlowError, match="not installed and responsive"):
        prepare_start(
            tmp_path,
            issue=11,
            project="Modern-Ash/agorix",
            agent="claude",
            workspace_factory=FakeWorkspace,
            runtime_discovery=lambda root: (runtime("codex"),),
        )


def test_prepare_start_reuses_existing_durable_issue_read_and_intent(tmp_path):
    workspace = FakeWorkspace(tmp_path)
    workspace._has_run = True
    workspace._works = [
        SimpleNamespace(
            id="issue-11",
            swarm_id="delivery",
            title="Deliver GitHub issue #11",
            path=str(tmp_path / ".agora" / "swarms" / "delivery" / "work" / "issue-11" / "WORK.md"),
            base_branch="main",
            branch="ai-sdlc/issue-11",
        )
    ]
    workspace._intent = SimpleNamespace(
        id="issue-11",
        path=str(tmp_path / ".agora" / "intents" / "issue-11" / "INTENT.md"),
        status="draft",
    )

    result = prepare_start(
        tmp_path,
        issue=11,
        project="Modern-Ash/agorix",
        workspace_factory=lambda cwd: workspace,
        runtime_discovery=lambda root: (runtime(),),
    )

    assert result.intent_id == "issue-11"
    assert len(workspace.created_work_inputs) == 0
    assert workspace.installed_adapters == []
    assert workspace.invocations == []


def test_documentation_issue_selects_documentation_pathway(tmp_path):
    workspace = FakeWorkspace(tmp_path)
    workspace._has_run = True

    def show_tool_run(run_id):
        payload = {
            "number": 9,
            "title": "Define child-facing content, feedback and first-mission copy",
            "body": "## Deliverable\n`docs/product/CONTENT_GUIDE.md`\n",
            "url": "https://github.com/Modern-Ash/agorix/issues/9",
        }
        return SimpleNamespace(result=SimpleNamespace(status="completed", stdout=json.dumps(payload), stderr=""))

    workspace.show_tool_run = show_tool_run
    result = prepare_start(
        tmp_path,
        issue=9,
        project="Modern-Ash/agorix",
        workspace_factory=lambda cwd: workspace,
        runtime_discovery=lambda root: (runtime(),),
    )

    assert result.pathway == "documentation"
    handoff = Path(result.handoff_path).read_text(encoding="utf-8")
    assert 'pathway: "documentation"' in handoff


def test_new_issue_branch_is_based_on_main_not_previous_issue_branch(tmp_path):
    if "branch" not in getattr(CreateWorkInput, "__dataclass_fields__", {}):
        pytest.skip("per-Work branch support requires Core 0.9+")

    _git_repo(tmp_path)
    _git(tmp_path, "switch", "-c", "feat/issue-12-program-model-schema")
    workspace = FakeWorkspace(tmp_path)
    workspace._has_run = True

    result = prepare_start(
        tmp_path,
        issue=13,
        project="Modern-Ash/agorix",
        workspace_factory=lambda cwd: workspace,
        runtime_discovery=lambda root: (runtime("claude"),),
    )

    created = workspace.created_work_inputs[0]
    assert created.base_branch == "main"
    assert created.branch == "ai-sdlc/issue-13"
    assert created.create_branch is True
    assert _git(tmp_path, "branch", "--show-current") == "main"
    assert result.base_branch == "main"


def test_new_issue_refuses_to_leave_dirty_previous_issue_branch(tmp_path):
    if "branch" not in getattr(CreateWorkInput, "__dataclass_fields__", {}):
        pytest.skip("per-Work branch support requires Core 0.9+")

    _git_repo(tmp_path)
    _git(tmp_path, "switch", "-c", "feat/issue-12-program-model-schema")
    (tmp_path / "README.md").write_text("# dirty issue 12\n", encoding="utf-8")
    workspace = FakeWorkspace(tmp_path)

    with pytest.raises(StartFlowError, match="commit or stash local changes first"):
        prepare_start(
            tmp_path,
            issue=13,
            project="Modern-Ash/agorix",
            workspace_factory=lambda cwd: workspace,
            runtime_discovery=lambda root: (runtime("claude"),),
        )

    assert workspace.created_work_inputs == []
    assert _git(tmp_path, "branch", "--show-current") == "feat/issue-12-program-model-schema"
