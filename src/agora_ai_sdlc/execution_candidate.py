"""ExecutionCandidate v1: the immutable subject a reviewer or verifier inspects.

Built on Core evidence primitives (`tested_commit`, artifact refs with content digests); it adds no
review authority, receipt store or gate. Core and method policy decide what the evidence means.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from agora.model import AddEvidenceInput

from agora_ai_sdlc.execution_envelope import EnvelopeError

CANDIDATE_SCHEMA = "agora-ai-sdlc/execution-candidate/v1"
KINDS = ("commit", "base-diff", "artifact-set", "worktree-snapshot")
MAX_MANIFEST_FILES = 500
MAX_FILE_BYTES = 1_000_000
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CandidateError(ValueError):
    """Typed candidate failure with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Candidate:
    repository: str
    swarm: str
    work: str
    revision: str
    kind: str
    target_commit: str | None
    base_commit: str | None
    changed_paths: tuple[str, ...]
    artifacts: tuple[tuple[str, str], ...]  # (uri, sha256), sorted

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise CandidateError("candidate.kind", f"unsupported candidate kind {self.kind!r}")
        for value, name in (
            (self.repository, "repository"),
            (self.swarm, "swarm"),
            (self.work, "work"),
            (self.revision, "revision"),
        ):
            if not value or not value.strip():
                raise CandidateError("candidate.identity", f"{name} is required")
        if self.kind in ("commit", "base-diff") and not (self.target_commit and _COMMIT.match(self.target_commit)):
            raise CandidateError("candidate.commit", f"{self.kind} candidate needs a full target commit")
        if self.kind == "base-diff" and not (self.base_commit and _COMMIT.match(self.base_commit)):
            raise CandidateError("candidate.base", "base-diff candidate needs a full base commit")
        if self.kind in ("artifact-set", "worktree-snapshot") and not self.artifacts:
            raise CandidateError("candidate.artifacts", f"{self.kind} candidate needs content-addressed artifacts")
        if len(self.artifacts) > MAX_MANIFEST_FILES:
            raise CandidateError("candidate.too_large", f"more than {MAX_MANIFEST_FILES} artifacts; split the review")
        if any(not _SHA256.match(digest) for _, digest in self.artifacts):
            raise CandidateError("candidate.digest", "artifact digests must be sha256 hex")

    @property
    def immutable(self) -> bool:
        """Commit and content-addressed candidates are immutable; a live worktree snapshot is not."""
        return self.kind != "worktree-snapshot"

    def identity(self) -> dict:
        return {
            "schema": CANDIDATE_SCHEMA,
            "repository": self.repository,
            "swarm": self.swarm,
            "work": self.work,
            "revision": self.revision,
            "kind": self.kind,
            "target_commit": self.target_commit,
            "base_commit": self.base_commit,
            "changed_paths": list(self.changed_paths),
            "artifacts": [{"uri": uri, "sha256": digest} for uri, digest in self.artifacts],
        }

    @property
    def subject_hash(self) -> str:
        payload = json.dumps(self.identity(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

    def descriptor(self) -> dict:
        """Adapter-facing immutable subject descriptor; adapters may not substitute HEAD or another ref."""
        return {
            **self.identity(),
            "subject_hash": self.subject_hash,
            "immutable": self.immutable,
            "limitations": None
            if self.immutable
            else (
                "live worktree snapshot: content is hashed at capture time and is not a Git commit; "
                "later edits make this candidate stale"
            ),
            "display": self.display(),
        }

    def display(self) -> str:
        head = (self.target_commit or "worktree")[:12]
        return f"{self.kind} {head} subject {self.subject_hash[:19]}"

    def envelope_reference(self) -> dict:
        return {"subject_hash": self.subject_hash, "kind": self.kind, "target_commit": self.target_commit}


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CandidateError("candidate.git", f"git unavailable: {error.__class__.__name__}") from error
    if result.returncode != 0:
        raise CandidateError("candidate.git", f"git {args[0]} failed")
    return result.stdout.strip()


def _digest(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise CandidateError("candidate.artifact_missing", f"artifact {path.name!r} is not a regular file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise CandidateError("candidate.too_large", f"artifact {path.name!r} exceeds {MAX_FILE_BYTES} bytes")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise CandidateError("candidate.path", f"path must stay inside the repository: {relative!r}")
    return root / path


def candidate_from_git(
    root: Path, *, repository: str, swarm: str, work: str, revision: str, target: str = "HEAD", base: str | None = None
) -> Candidate:
    """Commit-bound (or base-diff) candidate. Refs resolve to full commit ids now; live worktree edits are excluded."""
    target_commit = _git(root, "rev-parse", "--verify", f"{target}^{{commit}}")
    if base is None:
        paths = _git(root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", target_commit)
        kind, base_commit = "commit", None
    else:
        base_commit = _git(root, "rev-parse", "--verify", f"{base}^{{commit}}")
        paths = _git(root, "diff", "--name-only", base_commit, target_commit)
        kind = "base-diff"
    return Candidate(
        repository,
        swarm,
        work,
        revision,
        kind,
        target_commit,
        base_commit,
        tuple(sorted(p for p in paths.splitlines() if p)),
        (),
    )


def candidate_from_artifacts(
    root: Path, references: Sequence[str], *, repository: str, swarm: str, work: str, revision: str
) -> Candidate:
    """Artifact-set candidate: each reference is a repository-relative path hashed by content."""
    artifacts = tuple(sorted((ref, _digest(_safe_relative(root, ref))) for ref in dict.fromkeys(references)))
    return Candidate(repository, swarm, work, revision, "artifact-set", None, None, (), artifacts)


def candidate_from_worktree(root: Path, *, repository: str, swarm: str, work: str, revision: str) -> Candidate:
    """Explicit, bounded snapshot of uncommitted changes; not immutable and marked as such."""
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    tracked = _git(root, "diff", "--name-only", "HEAD").splitlines()
    untracked = _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    paths = sorted({p for p in (*tracked, *untracked) if p and (root / p).is_file()})
    if not paths:
        raise CandidateError("candidate.artifacts", "worktree has no changes to snapshot")
    artifacts = tuple((p, _digest(_safe_relative(root, p))) for p in paths)
    return Candidate(repository, swarm, work, revision, "worktree-snapshot", None, head, tuple(paths), artifacts)


def check_current(candidate: Candidate, current: Candidate) -> tuple[str, ...]:
    """Reasons a previously frozen candidate no longer applies to the current one (empty means it applies)."""
    reasons: list[str] = []
    if (candidate.swarm, candidate.work) != (current.swarm, current.work):
        reasons.append("candidate.work_changed")
    if candidate.revision != current.revision:
        reasons.append("candidate.revision_changed")
    if candidate.target_commit != current.target_commit or candidate.base_commit != current.base_commit:
        reasons.append("candidate.commit_changed")
    if candidate.artifacts != current.artifacts:
        reasons.append("candidate.artifact_changed")
    if candidate.changed_paths != current.changed_paths and "candidate.commit_changed" not in reasons:
        reasons.append("candidate.paths_changed")
    return tuple(reasons)


def require_current(candidate: Candidate, current: Candidate) -> None:
    reasons = check_current(candidate, current)
    if reasons:
        raise CandidateError("candidate.stale", ",".join(reasons))


def bind_envelope(payload: Mapping[str, Any], candidate: Candidate) -> None:
    """Adapter boundary: the envelope must reference exactly this candidate; no substitution."""
    reference = payload.get("candidate")
    if not isinstance(reference, Mapping) or reference.get("subject_hash") != candidate.subject_hash:
        raise EnvelopeError("envelope.candidate_mismatch", "envelope does not reference this candidate subject")


def review_evidence_input(
    candidate: Candidate,
    result: Mapping[str, Any],
    *,
    actor_id: str,
    evidence_type: str = "review",
    environment: str | None = None,
    session_id: str | None = None,
    require_immutable: bool = True,
) -> AddEvidenceInput:
    """Map a reviewer/verifier result to ordinary Core evidence bound to the exact subject.

    The result must carry the candidate's subject hash; Core stores `tested_commit` and artifact
    references (whose content digests Core records). No second approval record is created.
    """
    if result.get("subject_hash") != candidate.subject_hash:
        raise CandidateError("candidate.subject_missing", "result does not carry the candidate subject identity")
    if result.get("verdict") not in ("success", "failure"):
        raise CandidateError("candidate.verdict", "result verdict must be success or failure")
    if require_immutable and not candidate.immutable:
        raise CandidateError("candidate.not_immutable", "this workflow requires an immutable review subject")
    if not evidence_type.strip():
        raise CandidateError("candidate.evidence_type", "evidence type is required")
    optional = {}
    if session_id is not None and "session_id" in {field.name for field in fields(AddEvidenceInput)}:
        optional["session_id"] = session_id  # provenance only where the installed Core supports it
    return AddEvidenceInput(
        swarm_id=candidate.swarm,
        work_id=candidate.work,
        actor_id=actor_id,
        type=evidence_type,
        result=result["verdict"],
        artifact_refs=[uri for uri, _ in candidate.artifacts],
        evidence_id=f"{evidence_type}-{candidate.subject_hash[7:19]}",
        tested_commit=candidate.target_commit,
        environment=environment,
        dedupe_key=candidate.subject_hash,
        **optional,
    )
