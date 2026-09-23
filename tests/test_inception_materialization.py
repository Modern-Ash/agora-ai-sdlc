from pathlib import Path
from types import SimpleNamespace

import pytest

from agora_ai_sdlc.deterministic_inception import IssueFacts
from agora_ai_sdlc.inception_materialization import (
    GENERATED_MARKER,
    InceptionMaterializationError,
    materialize_deterministic_inception,
)


def issue() -> IssueFacts:
    return IssueFacts(
        title="Implement deterministic canonical program interpreter",
        objective="Execute learner programs without eval or generated-code execution.",
        requirements=(
            "deterministic state transitions",
            "explicit execution budget",
            "stop support",
            "no UI dependency",
            "no AI dependency",
            "no eval or arbitrary JavaScript execution",
        ),
        acceptance_criteria=(
            "tests for each operation",
            "nested repeat/if",
            "execution budget path",
            "deterministic repeated run",
            "stop outcome explicit",
        ),
        dependencies=("Program model + validation",),
        constraints=(
            "no UI dependency",
            "no AI dependency",
            "no eval or arbitrary JavaScript execution",
        ),
        semantic_gaps=(),
    )


class Workspace:
    def __init__(self):
        self.records = []
        self.added = []
        self.satisfied = []
        self.work = SimpleNamespace(
            acceptance_criteria={"source-issue": "Satisfy source issue"},
            criterion_statuses={"source-issue": []},
        )

    def show_swarm(self, swarm_id):
        return SimpleNamespace(assignments={"developer": "project:ai-opencode"})

    def list_work_artifacts(self, swarm_id, work_id):
        return list(self.records)

    def add_artifact(self, data):
        self.added.append(data)
        self.records.append(
            SimpleNamespace(
                kind=data.kind,
                uri=data.uri,
                content_sha256=data.content_sha256,
            )
        )

    def show_work(self, swarm_id, work_id):
        return self.work

    def satisfy_criterion(self, data, criterion_id, stage=None):
        self.satisfied.append((data, criterion_id, stage))
        self.work.criterion_statuses.setdefault(criterion_id, []).append(stage)


def setup_intent(root: Path) -> Path:
    path = root / ".agora" / "intents" / "issue-14" / "INTENT.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Intent\n\nCanonical interpreter.\n", encoding="utf-8")
    return path


def test_materializes_required_artifacts_and_elaborates_source_issue(tmp_path: Path):
    intent = setup_intent(tmp_path)
    workspace = Workspace()

    result = materialize_deterministic_inception(
        tmp_path,
        workspace=workspace,
        swarm_id="delivery",
        work_id="issue-14",
        intent_path=str(intent),
        issue=issue(),
        pathway="brownfield",
    )

    assert result.actor_id == "project:ai-opencode"
    assert {item.kind for item in workspace.added} == {
        "intent",
        "requirements",
        "unit-of-work",
    }
    assert result.intent_uri == "repo://.agora/intents/issue-14/INTENT.md"
    assert result.requirements_uri == "repo://.agora/intents/issue-14/REQUIREMENTS.md"
    assert result.unit_of_work_uri == "repo://.agora/intents/issue-14/UNIT-OF-WORK.md"

    requirements = intent.parent / "REQUIREMENTS.md"
    unit_of_work = intent.parent / "UNIT-OF-WORK.md"
    assert requirements.read_text(encoding="utf-8").startswith(GENERATED_MARKER)
    assert "deterministic state transitions" in requirements.read_text(encoding="utf-8")
    assert unit_of_work.read_text(encoding="utf-8").startswith(GENERATED_MARKER)
    assert "Pathway: brownfield" in unit_of_work.read_text(encoding="utf-8")

    assert len(workspace.satisfied) == 1
    actor, criterion, stage = workspace.satisfied[0]
    assert actor.actor_id == "project:ai-opencode"
    assert criterion == "source-issue"
    assert stage == "elaborated"

    assert "artifact.registered:intent" in result.actions
    assert "artifact.registered:requirements" in result.actions
    assert "artifact.registered:unit-of-work" in result.actions
    assert "criterion.elaborated:source-issue" in result.actions


def test_materialization_is_idempotent(tmp_path: Path):
    intent = setup_intent(tmp_path)
    workspace = Workspace()

    first = materialize_deterministic_inception(
        tmp_path,
        workspace=workspace,
        swarm_id="delivery",
        work_id="issue-14",
        intent_path=str(intent),
        issue=issue(),
        pathway="brownfield",
    )
    second = materialize_deterministic_inception(
        tmp_path,
        workspace=workspace,
        swarm_id="delivery",
        work_id="issue-14",
        intent_path=str(intent),
        issue=issue(),
        pathway="brownfield",
    )

    assert first.actions
    assert second.actions == ()
    assert len(workspace.records) == 3
    assert len(workspace.satisfied) == 1


def test_materialization_refuses_to_overwrite_manual_requirements(tmp_path: Path):
    intent = setup_intent(tmp_path)
    manual = intent.parent / "REQUIREMENTS.md"
    manual.write_text("# Human requirements\n\nKeep this.\n", encoding="utf-8")
    workspace = Workspace()

    with pytest.raises(InceptionMaterializationError, match="refusing to overwrite"):
        materialize_deterministic_inception(
            tmp_path,
            workspace=workspace,
            swarm_id="delivery",
            work_id="issue-14",
            intent_path=str(intent),
            issue=issue(),
            pathway="brownfield",
        )

    assert manual.read_text(encoding="utf-8") == "# Human requirements\n\nKeep this.\n"
    assert workspace.added == []
    assert workspace.satisfied == []
