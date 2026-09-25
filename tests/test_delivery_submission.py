from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc import delivery_submission
from agora_ai_sdlc.delivery_submission import work_change_set
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.wizard_actions import execute_in_session_action, next_in_session_action


def decision(**changes):
    values = {
        "swarm": "delivery",
        "work": "issue-14",
        "title": "Deliver GitHub issue #14",
        "method": "ai-sdlc",
        "actor": "project:product-owner",
        "role": "product-owner",
        "state": "operations",
        "target": "completed",
        "gate": "completion",
        "blockers": ("unsatisfied=[source-issue]", "missing-evidence-types=[deployment]"),
        "messages": ("Complete criteria.",),
        "missing_artifacts": (),
        "missing_evidence": ("deployment",),
        "missing_approvals": (),
        "unsatisfied_criteria": ("source-issue",),
        "git_issues": (),
        "clarification_issues": (),
        "ready_for_human_approval": False,
        "ready_to_transition": False,
        "criterion_statuses": (("source-issue", ("elaborated", "designed", "built", "verified")),),
        "developer_actor": "project:ai-codex",
        "developer_actor_kind": "ai-agent",
        "responsible_actor_kind": "human",
    }
    values.update(changes)
    return GuidedDecision(**values)


def test_work_change_set_excludes_unrelated_agora_history(monkeypatch, tmp_path: Path):
    def fake_git(root, *args, check=True):
        key = tuple(args)
        if key[:2] == ("diff", "--name-only"):
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    "packages/runtime/src/index.ts\n"
                    ".agora/intents/issue-14/INTENT.md\n"
                    ".agora/intents/issue-8/INTENT.md\n"
                    ".agora/activity.md\n"
                ),
                stderr="",
            )
        if key[:3] == ("diff", "--cached", "--name-only"):
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if key[:2] == ("ls-files", "--others"):
            return SimpleNamespace(
                returncode=0,
                stdout=(".agora/ai-sdlc/handoffs/issue-14/REVIEW.md\n.agora/sessions/unrelated/RESULT.md\n"),
                stderr="",
            )
        raise AssertionError(key)

    monkeypatch.setattr(delivery_submission, "_git", fake_git)

    assert work_change_set(tmp_path, "issue-14") == (
        "packages/runtime/src/index.ts",
        ".agora/intents/issue-14/INTENT.md",
        ".agora/ai-sdlc/handoffs/issue-14/REVIEW.md",
    )


def test_operations_pull_request_is_a_flow_action(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "agora_ai_sdlc.wizard_actions.pull_request_delivery_enabled",
        lambda root: True,
    )
    assert next_in_session_action(decision(), root=tmp_path) == "submit-pr"


def test_submit_pr_action_is_executed_inside_flow(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "agora_ai_sdlc.wizard_actions.pull_request_delivery_enabled",
        lambda root: True,
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.wizard_actions.submit_pull_request",
        lambda root, current, workspace_factory=None: SimpleNamespace(
            pull_request_url="https://github.com/Modern-Ash/agorix/pull/42",
            branch="ai-sdlc/issue-14",
            commit_sha="abcdef1234567890",
        ),
    )

    result = execute_in_session_action(
        tmp_path,
        decision(),
        workspace_factory=lambda cwd: object(),
    )

    assert result.kind == "pull_request_submitted"
    assert result.details == (
        ("url", "https://github.com/Modern-Ash/agorix/pull/42"),
        ("branch", "ai-sdlc/issue-14"),
        ("commit", "abcdef123456"),
    )
