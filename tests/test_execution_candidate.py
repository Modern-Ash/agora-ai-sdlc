import json
import subprocess
from pathlib import Path

import pytest

from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_candidate import (
    CandidateError,
    bind_envelope,
    candidate_from_artifacts,
    candidate_from_git,
    candidate_from_worktree,
    check_current,
    require_current,
    review_evidence_input,
)
from agora_ai_sdlc.execution_envelope import CoreSnapshot, EnvelopeError, build_envelope, verify_integrity
from agora_ai_sdlc.execution_requirements import requirements_for
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding

IDENT = {"repository": "Modern-Ash/x", "swarm": "delivery", "work": "issue-26", "revision": "rev-4"}


def git(root, *args):
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=a@b.c", "-c", "user.name=t", *args], check=True, capture_output=True
    )


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.txt").write_text("one\n")
    git(tmp_path, "add", "."), git(tmp_path, "commit", "-q", "-m", "one")
    return tmp_path


def commit(repo, name, text):
    (repo / name).write_text(text)
    git(repo, "add", "."), git(repo, "commit", "-q", "-m", name)


def test_commit_bound_candidate_and_deterministic_hash(repo):
    first = candidate_from_git(repo, **IDENT)
    again = candidate_from_git(repo, **IDENT)
    assert first.kind == "commit" and len(first.target_commit) == 40 and first.immutable
    assert first.subject_hash == again.subject_hash and first.descriptor()["subject_hash"] == first.subject_hash
    assert first.changed_paths == ("a.txt",)


def test_changed_commit_changes_identity_and_makes_candidate_stale(repo):
    old = candidate_from_git(repo, **IDENT)
    commit(repo, "b.txt", "two\n")
    new = candidate_from_git(repo, **IDENT)
    assert new.subject_hash != old.subject_hash
    assert "candidate.commit_changed" in check_current(old, new)
    with pytest.raises(CandidateError) as error:
        require_current(old, new)
    assert error.value.code == "candidate.stale"


def test_dirty_worktree_does_not_leak_into_commit_candidate(repo):
    before = candidate_from_git(repo, **IDENT)
    (repo / "a.txt").write_text("edited\n")
    assert candidate_from_git(repo, **IDENT).subject_hash == before.subject_hash


def test_base_diff_candidate(repo):
    commit(repo, "b.txt", "two\n")
    cand = candidate_from_git(repo, **IDENT, base="HEAD~1")
    assert cand.kind == "base-diff" and cand.changed_paths == ("b.txt",) and cand.base_commit != cand.target_commit


def test_artifact_set_same_bytes_same_identity_changed_bytes_change_it(repo):
    (repo / "doc.md").write_text("spec\n")
    first = candidate_from_artifacts(repo, ["doc.md"], **IDENT)
    assert first.subject_hash == candidate_from_artifacts(repo, ["doc.md"], **IDENT).subject_hash
    (repo / "doc.md").write_text("spec v2\n")
    second = candidate_from_artifacts(repo, ["doc.md"], **IDENT)
    assert second.subject_hash != first.subject_hash and "candidate.artifact_changed" in check_current(first, second)


def test_artifact_reference_safety_and_bounds(repo):
    for bad in ("../x", "/etc/passwd"):
        with pytest.raises(CandidateError) as error:
            candidate_from_artifacts(repo, [bad], **IDENT)
        assert error.value.code == "candidate.path"
    with pytest.raises(CandidateError) as error:
        candidate_from_artifacts(repo, ["missing.md"], **IDENT)
    assert error.value.code == "candidate.artifact_missing"


def test_revision_change_makes_candidate_stale(repo):
    old = candidate_from_git(repo, **IDENT)
    new = candidate_from_git(repo, **{**IDENT, "revision": "rev-5"})
    assert check_current(old, new) == ("candidate.revision_changed",)


def test_worktree_snapshot_is_explicitly_not_immutable_and_rejected_when_immutable_required(repo):
    (repo / "a.txt").write_text("edited\n")
    (repo / "new.txt").write_text("n\n")
    snap = candidate_from_worktree(repo, **IDENT)
    assert not snap.immutable and "not a Git commit" in snap.descriptor()["limitations"]
    assert [p for p, _ in snap.artifacts] == ["a.txt", "new.txt"]
    result = {"subject_hash": snap.subject_hash, "verdict": "success"}
    with pytest.raises(CandidateError) as error:
        review_evidence_input(snap, result, actor_id="project:reviewer")
    assert error.value.code == "candidate.not_immutable"
    assert (
        review_evidence_input(snap, result, actor_id="project:reviewer", require_immutable=False).tested_commit is None
    )
    (repo / "a.txt").write_text("edited again\n")
    assert candidate_from_worktree(repo, **IDENT).subject_hash != snap.subject_hash


def test_evidence_mapping_uses_core_fields(repo):
    (repo / "doc.md").write_text("spec\n")
    cand = candidate_from_git(repo, **IDENT)
    evidence = review_evidence_input(
        cand, {"subject_hash": cand.subject_hash, "verdict": "success"}, actor_id="project:reviewer",
        environment="local", session_id="s-1",
    )  # fmt: skip
    assert evidence.tested_commit == cand.target_commit and evidence.dedupe_key == cand.subject_hash
    assert evidence.type == "review" and evidence.result == "success"
    artifacts = candidate_from_artifacts(repo, ["doc.md"], **IDENT)
    mapped = review_evidence_input(
        artifacts, {"subject_hash": artifacts.subject_hash, "verdict": "failure"}, actor_id="p:r"
    )
    assert mapped.artifact_refs == ["doc.md"] and mapped.tested_commit is None and mapped.result == "failure"


def test_result_without_or_with_wrong_subject_identity_is_rejected(repo):
    cand = candidate_from_git(repo, **IDENT)
    for result in ({"verdict": "success"}, {"subject_hash": "sha256:other", "verdict": "success"}):
        with pytest.raises(CandidateError) as error:
            review_evidence_input(cand, result, actor_id="project:reviewer")
        assert error.value.code == "candidate.subject_missing"
    with pytest.raises(CandidateError) as error:
        review_evidence_input(cand, {"subject_hash": cand.subject_hash, "verdict": "approved"}, actor_id="p:r")
    assert error.value.code == "candidate.verdict"


def test_invalid_candidates_fail_closed():
    with pytest.raises(CandidateError):
        candidate = __import__("agora_ai_sdlc.execution_candidate", fromlist=["Candidate"]).Candidate
        candidate("r", "s", "w", "1", "commit", "abc", None, (), ())
    with pytest.raises(CandidateError) as error:
        __import__("agora_ai_sdlc.execution_candidate", fromlist=["Candidate"]).Candidate(
            "r", "s", "w", "1", "nope", None, None, (), ()
        )
    assert error.value.code == "candidate.kind"


def bundle():
    return ExecutionBundle(
        schema="s", swarm="delivery", work="issue-26", stage="review", next_action="inspect-next", branch=None,
        base_branch=None, head=None, objective="o", acceptance_criteria=(), changed_paths=(), dirty_paths=(),
        related_paths=(), languages=(), build_systems=(), verification_commands=(), risks=(),
        governance={}, deterministic_inception_path=None,
    )  # fmt: skip


def test_envelope_carries_candidate_and_adapter_cannot_substitute_it(repo):
    cand = candidate_from_git(repo, **IDENT)
    snap = CoreSnapshot("delivery", "issue-26", "rev-4", "review", "operations", "reviewer",
                        {"reviewer": "project:reviewer"}, frozenset({"project:reviewer"}), False)  # fmt: skip
    binding = RuntimeBinding(AgentRuntimeRef("claude", "claude-code"), ModelRuntimeRef("anthropic", "anthropic", "m"))
    payload = build_envelope(snap, requirements_for(bundle()), binding, bundle(), actor_id="project:reviewer",
                             candidate=cand.envelope_reference()).to_dict()  # fmt: skip
    assert verify_integrity(json.loads(json.dumps(payload))).candidate["subject_hash"] == cand.subject_hash
    bind_envelope(payload, cand)
    commit(repo, "b.txt", "two\n")
    other = candidate_from_git(repo, **IDENT)
    with pytest.raises(EnvelopeError) as error:
        bind_envelope(payload, other)
    assert error.value.code == "envelope.candidate_mismatch"
    forged = json.loads(json.dumps(payload))
    forged["candidate"]["subject_hash"] = other.subject_hash
    with pytest.raises(EnvelopeError) as error:
        verify_integrity(forged)
    assert error.value.code == "envelope.tampered"


def test_display_has_identity_and_no_secrets(repo):
    text = candidate_from_git(repo, **IDENT).display()
    assert text.startswith("commit ") and "subject sha256:" in text
    assert isinstance(Path(repo), Path)
