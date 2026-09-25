import json
from pathlib import Path
from types import SimpleNamespace

import yaml
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.brief_flow import prepare_brief_start
from agora_ai_sdlc.guided import GuidedDecision, inspect_next
from agora_ai_sdlc.local_delivery import capture_local_baseline, publish_local_artifacts
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery


def runtime() -> RuntimeDiscovery:
    return RuntimeDiscovery(
        id="codex",
        name="Codex",
        command="codex",
        installed=True,
        executable="/usr/bin/codex",
        responsive=True,
        version="1.0",
        configured=True,
    )


def test_brief_start_bootstraps_gitless_project(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    project = tmp_path / "calculator-demo"
    project.mkdir()
    brief = project / "INTENT_BRIEF.md"
    brief.write_text(
        """# Percentage Discount Calculator

## Objective

Calculate the final price after applying a percentage discount.

## Requirements

- price must be zero or greater
- percentage must be between 0 and 100
- deterministic result

## Acceptance criteria

- 100 with 10 percent returns 90
- negative price is rejected
- percentage above 100 is rejected

## Constraints

- TypeScript
- unit tests required
- no external services
""",
        encoding="utf-8",
    )

    result = prepare_brief_start(
        project,
        brief=Path("INTENT_BRIEF.md"),
        agent="codex",
        runtime_discovery=lambda root: (runtime(),),
    )

    assert not (project / ".git").exists()
    assert result.source_kind == "intent-brief"
    assert result.work_id == "percentage-discount-calculator"
    assert result.swarm_id == "delivery"
    assert result.output_path.endswith("output/percentage-discount-calculator")
    assert Path(result.intent_path).is_file()
    assert Path(result.deterministic_inception_path).is_file()
    assert Path(result.baseline_path).is_file()

    config = yaml.safe_load((project / "ai-sdlc" / "project.yaml").read_text(encoding="utf-8"))
    assert config["pathway"] == "new-product"
    assert config["integrations"] == []
    assert config["delivery_target"]["type"] == "local-artifacts"

    baseline = json.loads(Path(result.baseline_path).read_text(encoding="utf-8"))
    assert "INTENT_BRIEF.md" in baseline["files"]

    workspace = AgoraWorkspace(cwd=project)
    artifact_kinds = {item.kind for item in workspace.list_work_artifacts(result.swarm_id, result.work_id)}
    assert artifact_kinds == {
        "intent",
        "plan",
        "requirements",
        "user-stories",
        "nfr",
        "risk-register",
        "measurement-criteria",
        "unit-of-work",
        "bolt-plan",
    }
    for filename in (
        "PLAN.md",
        "USER-STORIES.md",
        "NFR.md",
        "RISK-REGISTER.md",
        "MEASUREMENT-CRITERIA.md",
        "BOLT-PLAN.md",
    ):
        assert (Path(result.intent_path).parent / filename).is_file()

    decision = inspect_next(project, swarm=result.swarm_id, work=result.work_id)
    assert decision is not None
    assert decision.state == "inception"
    assert decision.missing_artifacts == ()
    assert set(decision.missing_approvals) == {"product-owner", "developer"}
    assert decision.ready_for_human_approval is True


def test_local_delivery_copies_only_files_changed_after_baseline(tmp_path: Path):
    root = tmp_path
    (root / "INTENT_BRIEF.md").write_text("# Demo\n", encoding="utf-8")
    capture_local_baseline(root, "demo")

    source = root / "src" / "calculator.ts"
    source.parent.mkdir()
    source.write_text("export const add = (a: number, b: number) => a + b;\n", encoding="utf-8")

    calls = {"evidence": [], "criteria": []}

    class Workspace:
        def __init__(self, cwd):
            self.cwd = cwd

        def add_evidence(self, data):
            calls["evidence"].append(data)

        def satisfy_criterion(self, data, criterion, *, stage=None):
            calls["criteria"].append((data.actor_id, criterion, stage))

    decision = GuidedDecision(
        swarm="delivery",
        work="demo",
        title="Demo",
        method="ai-sdlc",
        actor="project:product-owner",
        role="product-owner",
        state="operations",
        target="completed",
        gate="completion",
        blockers=("unsatisfied=[source-issue]", "missing-evidence-types=[deployment]"),
        messages=("Publish result.",),
        missing_artifacts=(),
        missing_evidence=("deployment",),
        missing_approvals=(),
        unsatisfied_criteria=("source-issue",),
        git_issues=(),
        clarification_issues=(),
        criterion_statuses=(("source-issue", ("elaborated", "designed", "built", "verified")),),
        developer_actor="project:ai-codex",
        developer_actor_kind="ai-agent",
    )

    result = publish_local_artifacts(root, decision, workspace_factory=Workspace)

    assert result.product_files == ("src/calculator.ts",)
    assert (root / "output" / "demo" / "product" / "src" / "calculator.ts").is_file()
    manifest = Path(result.manifest_path).read_text(encoding="utf-8")
    assert "product/src/calculator.ts" in manifest
    assert "INTENT_BRIEF.md" not in manifest
    assert calls["evidence"][0].environment == "local-artifacts"
    assert calls["criteria"] == [("project:ai-codex", "source-issue", "deployed")]
