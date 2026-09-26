"""Fail closed when an executor run leaves Agora governed state worse than it found it.

Executors may legitimately mutate `.agora/` through governed CLI commands, so the guard compares
Core validation before and after the run and only blocks issues the run introduced (for example an
`INTENT.md` overwritten without its front matter). Pre-existing issues never block a run.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from agora.workspace import AgoraWorkspace

IssueKey = tuple[str, str]


class GovernanceRegression(Exception):
    """The run introduced governance validation errors; `issues` holds (code, path, message)."""

    def __init__(self, issues: list[tuple[str, str, str]], *, code: str = "governance.regression") -> None:
        self.code = code
        self.issues = issues
        listed = "; ".join(f"{item_code} at {path}" for item_code, path, _ in issues[:5])
        more = "" if len(issues) <= 5 else f"; +{len(issues) - 5} more"
        super().__init__(
            f"{code}: the executor run left governed state invalid ({listed}{more}). "
            "Restore the affected files (git diff .agora/) before continuing; nothing was approved."
        )


def _error_issues(report: Any) -> dict[IssueKey, str]:
    return {
        (issue.code, issue.path): str(issue.message)
        for issue in report.issues
        if str(getattr(issue.severity, "value", issue.severity)) == "error"
    }


def _validate(root: Path, factory: Callable[..., Any]) -> dict[IssueKey, str] | None:
    try:
        return _error_issues(factory(cwd=root).validate())
    except (OSError, ValueError, RuntimeError):
        return None


@contextmanager
def guard_governed_state(root: Path, *, workspace_factory: Callable[..., Any] = AgoraWorkspace) -> Iterator[None]:
    """Raise GovernanceRegression after the block if it introduced new validation errors."""
    before = _validate(root, workspace_factory)
    yield
    if before is None:
        return  # no trustworthy baseline; do not block on unrelated pre-existing breakage
    after = _validate(root, workspace_factory)
    if after is None:
        raise GovernanceRegression([], code="governance.validation_unavailable")
    introduced = [(code, path, after[(code, path)]) for code, path in sorted(after) if (code, path) not in before]
    if introduced:
        raise GovernanceRegression(introduced)
