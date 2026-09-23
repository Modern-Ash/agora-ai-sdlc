import json
import shlex
import subprocess

import pytest

from agora_ai_sdlc.deterministic_clarification import (
    _zero_question_runner,
    record_zero_question_clarification,
)


class Workspace:
    def __init__(self):
        self.calls = []

    def clarify_work(self, data, *, runner=None):
        self.calls.append((data, runner))
        command = shlex.split(runner)
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(completed.stdout)


def test_zero_question_runner_returns_canonical_empty_questions():
    completed = subprocess.run(
        shlex.split(_zero_question_runner()),
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(completed.stdout) == {"questions": []}


def test_record_zero_question_clarification_uses_core_runner_contract():
    workspace = Workspace()

    result = record_zero_question_clarification(
        workspace=workspace,
        swarm_id="delivery",
        work_id="issue-26",
        actor_id="project:ai-claude",
    )

    assert result.actions == ("clarification.resolved:deterministic-zero-question",)
    assert len(workspace.calls) == 1
    data, runner = workspace.calls[0]
    assert data.swarm_id == "delivery"
    assert data.work_id == "issue-26"
    assert data.actor_id == "project:ai-claude"
    assert "deterministic_advisor" in runner


def test_record_zero_question_clarification_requires_actor():
    with pytest.raises(ValueError, match="assigned developer actor"):
        record_zero_question_clarification(
            workspace=Workspace(),
            swarm_id="delivery",
            work_id="issue-26",
            actor_id="",
        )
