from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc.construction_reconciliation import (
    CONSTRUCTION_ARTIFACTS,
    reconcile_construction_execution,
)
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.local_delivery import capture_local_baseline


def decision() -> GuidedDecision:
    return GuidedDecision(
        swarm="delivery",
        work="percentage-discount-calculator",
        title="Percentage Discount Calculator",
        method="ai-sdlc",
        actor="project:ai-opencode",
        role="developer",
        state="construction",
        target="operations",
        gate="construction-verified",
        blockers=(),
        messages=(),
        missing_artifacts=tuple(kind for kind, _ in CONSTRUCTION_ARTIFACTS),
        missing_evidence=("test-suite",),
        missing_approvals=("developer",),
        unsatisfied_criteria=("source-issue",),
        git_issues=(),
        clarification_issues=(),
        criterion_statuses=(("source-issue", ("elaborated",)),),
        developer_actor="project:ai-opencode",
        developer_actor_kind="ai-agent",
    )


def test_reconciliation_registers_observable_outputs_and_verified_progress(monkeypatch, tmp_path: Path):
    capture_local_baseline(tmp_path, "percentage-discount-calculator")

    construction = tmp_path / ".agora" / "ai-sdlc" / "construction" / "percentage-discount-calculator"
    construction.mkdir(parents=True)
    for kind, filename in CONSTRUCTION_ARTIFACTS:
        (construction / filename).write_text(f"# {kind}\n\nConcrete content.\n", encoding="utf-8")

    source = tmp_path / "src" / "discount.ts"
    source.parent.mkdir(parents=True)
    source.write_text("export const discount = () => 90;\n", encoding="utf-8")
    test = tmp_path / "tests" / "discount.test.ts"
    test.parent.mkdir(parents=True)
    test.write_text("test('discount', () => {});\n", encoding="utf-8")

    class Workspace:
        def __init__(self, cwd):
            self.cwd = cwd
            self.records = []
            self.evidence = []
            self.work = SimpleNamespace(
                criterion_statuses={"source-issue": ["elaborated"]},
            )

        def list_work_artifacts(self, swarm, work):
            return list(self.records)

        def add_artifact(self, data):
            self.records.append(
                SimpleNamespace(
                    kind=data.kind,
                    uri=data.uri,
                    content_sha256=data.content_sha256,
                )
            )

        def show_work(self, swarm, work):
            return self.work

        def satisfy_criterion(self, data, criterion, *, stage=None):
            self.work.criterion_statuses.setdefault(criterion, []).append(stage)

        def add_evidence(self, data):
            self.evidence.append(data)

    workspace = Workspace(tmp_path)
    verification_path = (
        tmp_path / ".agora" / "ai-sdlc" / "verification" / "percentage-discount-calculator" / "VERIFICATION.json"
    )
    verification_path.parent.mkdir(parents=True, exist_ok=True)
    verification_path.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        "agora_ai_sdlc.construction_reconciliation.build_verification_report",
        lambda *args, **kwargs: SimpleNamespace(
            commands=(SimpleNamespace(status="passed"), SimpleNamespace(status="passed")),
            all_executed_commands_passed=True,
            report_path=str(verification_path),
        ),
    )

    result = reconcile_construction_execution(
        tmp_path,
        decision(),
        workspace_factory=lambda cwd: workspace,
    )

    assert set(result.registered_artifacts) == {kind for kind, _ in CONSTRUCTION_ARTIFACTS}
    assert "src/discount.ts" in result.changed_product_files
    assert "tests/discount.test.ts" in result.changed_product_files
    assert result.criterion_stages == ("designed", "built", "verified")
    assert result.verification_passed is True
    assert workspace.work.criterion_statuses["source-issue"] == [
        "elaborated",
        "designed",
        "built",
        "verified",
    ]
    assert len(workspace.evidence) == 1
    assert workspace.evidence[0].type == "test-suite"
    assert workspace.evidence[0].result == "success"


def test_reconciliation_does_not_invent_progress_without_observable_files(tmp_path: Path):
    capture_local_baseline(tmp_path, "percentage-discount-calculator")

    class Workspace:
        def __init__(self, cwd):
            self.work = SimpleNamespace(criterion_statuses={"source-issue": ["elaborated"]})

        def list_work_artifacts(self, swarm, work):
            return []

        def show_work(self, swarm, work):
            return self.work

    result = reconcile_construction_execution(
        tmp_path,
        decision(),
        workspace_factory=Workspace,
    )

    assert result.registered_artifacts == ()
    assert result.changed_product_files == ()
    assert result.criterion_stages == ()
    assert result.verification_passed is False
