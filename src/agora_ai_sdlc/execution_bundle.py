"""Deterministic Construction/Review context bundle with no LLM calls."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.deterministic_inception import inspect_repository
from agora_ai_sdlc.iteration_status import inspect_iteration

SCHEMA = "agora-ai-sdlc/execution-bundle/v1"
MAX_RELATED_PATHS = 24
MAX_KEYWORDS = 10
STOP_WORDS = {
    "acceptance",
    "and",
    "canonical",
    "criteria",
    "deliver",
    "deterministic",
    "execute",
    "from",
    "implement",
    "implementation",
    "issue",
    "must",
    "program",
    "the",
    "this",
    "with",
}
RISK_PATTERNS = (
    ("ci-configuration", re.compile(r"^(?:\.github/workflows/|\.gitlab-ci\.yml$)")),
    (
        "dependency-or-build-change",
        re.compile(r"(?:^|/)(?:pom\.xml|build\.gradle(?:\.kts)?|package(?:-lock)?\.json|pyproject\.toml)$"),
    ),
    ("database-migration", re.compile(r"(?:^|/)(?:migrations?|db/migration|liquibase|flyway)(?:/|$)", re.IGNORECASE)),
    ("security-sensitive", re.compile(r"(?:auth|oauth|security|permission|credential|secret)", re.IGNORECASE)),
    (
        "deployment-or-infrastructure",
        re.compile(r"(?:^|/)(?:Dockerfile|docker-compose|terraform|infra|k8s|helm)(?:[./]|$)", re.IGNORECASE),
    ),
)


class ExecutionBundleError(ValueError):
    """Stable error while assembling deterministic execution context."""


@dataclass(frozen=True)
class ExecutionBundle:
    schema: str
    swarm: str | None
    work: str | None
    stage: str | None
    next_action: str
    branch: str | None
    base_branch: str | None
    head: str | None
    objective: str | None
    acceptance_criteria: tuple[str, ...]
    changed_paths: tuple[str, ...]
    dirty_paths: tuple[str, ...]
    related_paths: tuple[str, ...]
    languages: tuple[str, ...]
    build_systems: tuple[str, ...]
    verification_commands: tuple[str, ...]
    risks: tuple[str, ...]
    governance: dict
    deterministic_inception_path: str | None
    json_path: str | None = None
    markdown_path: str | None = None

    def snapshot(self) -> dict:
        return asdict(self)


def _git(root: Path, *args: str, timeout: float = 5.0) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _git_lines(root: Path, *args: str) -> tuple[str, ...]:
    code, stdout, _ = _git(root, *args)
    if code != 0 or not stdout:
        return ()
    return tuple(line for line in stdout.splitlines() if line.strip())


def _head(root: Path) -> str | None:
    code, stdout, _ = _git(root, "rev-parse", "HEAD")
    return stdout if code == 0 and stdout else None


def _status_paths(root: Path) -> tuple[str, ...]:
    lines = _git_lines(root, "status", "--porcelain=v1", "--untracked-files=all")
    values: list[str] = []
    for line in lines:
        if len(line) < 4:
            continue
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        values.append(value.strip())
    return tuple(dict.fromkeys(values))


def _changed_paths(root: Path, base_branch: str | None) -> tuple[str, ...]:
    if not base_branch:
        return ()
    candidates = (base_branch, f"origin/{base_branch}")
    for candidate in candidates:
        code, _, _ = _git(root, "rev-parse", "--verify", candidate)
        if code != 0:
            continue
        lines = _git_lines(root, "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{candidate}...HEAD")
        return tuple(dict.fromkeys(lines))
    return ()


def _section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n+(.*?)(?=^##\s+|\Z)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _inception_facts(root: Path, work: str | None) -> tuple[str | None, tuple[str, ...], str | None]:
    if not work:
        return None, (), None
    path = root / ".agora" / "ai-sdlc" / "handoffs" / work / "DETERMINISTIC_INCEPTION.md"
    if not path.is_file():
        return None, (), None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, (), None
    objective = _section(text, "Intent interpretation") or None
    trace = _section(text, "Acceptance criteria trace")
    criteria: list[str] = []
    for raw in trace.splitlines():
        line = raw.strip()
        match = re.match(r"^-\s+AC-\d+:\s+(.*?)\s+->\s+plan step", line)
        if match:
            criteria.append(match.group(1).strip())
    return objective, tuple(criteria), str(path)


def _keywords(objective: str | None, criteria: tuple[str, ...]) -> tuple[str, ...]:
    source = " ".join((objective or "", *criteria)).casefold()
    tokens = re.findall(r"[a-z][a-z0-9_-]{3,}", source)
    selected: list[str] = []
    for token in tokens:
        if token in STOP_WORDS or token in selected:
            continue
        selected.append(token)
        if len(selected) >= MAX_KEYWORDS:
            break
    return tuple(selected)


def _tracked_paths(root: Path) -> tuple[str, ...]:
    return _git_lines(root, "ls-files")


def _grep_paths(root: Path, keywords: tuple[str, ...]) -> tuple[str, ...]:
    if not keywords:
        return ()
    expression = "|".join(re.escape(keyword) for keyword in keywords)
    code, stdout, _ = _git(root, "grep", "-l", "-I", "-E", expression, "--")
    if code not in {0, 1} or not stdout:
        return ()
    return tuple(line for line in stdout.splitlines() if line.strip())


def _related_paths(
    root: Path,
    *,
    keywords: tuple[str, ...],
    changed_paths: tuple[str, ...],
    dirty_paths: tuple[str, ...],
) -> tuple[str, ...]:
    tracked = _tracked_paths(root)
    grep = set(_grep_paths(root, keywords))
    changed = set(changed_paths)
    dirty = set(dirty_paths)
    scored: list[tuple[int, str]] = []

    for path in tracked:
        lowered = path.casefold()
        score = 0
        if path in changed:
            score += 100
        if path in dirty:
            score += 80
        if path in grep:
            score += 30
        score += sum(5 for keyword in keywords if keyword in lowered)
        if "/test/" in lowered or "/tests/" in lowered or "test_" in Path(path).name.casefold():
            score += 2
        if score:
            scored.append((score, path))

    for path in (*changed_paths, *dirty_paths):
        if path not in tracked:
            scored.append((120, path))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(dict.fromkeys(path for _, path in scored))[:MAX_RELATED_PATHS]


def _risk_flags(
    *,
    changed_paths: tuple[str, ...],
    dirty_paths: tuple[str, ...],
    repository_test_files: int,
) -> tuple[str, ...]:
    risks: list[str] = []
    material = tuple(dict.fromkeys((*changed_paths, *dirty_paths)))
    for code, pattern in RISK_PATTERNS:
        if any(pattern.search(path) for path in material):
            risks.append(code)

    source_changes = [
        path
        for path in material
        if Path(path).suffix.casefold() in {".java", ".kt", ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
        and "/test/" not in path.casefold()
        and "/tests/" not in path.casefold()
        and not Path(path).name.casefold().startswith("test_")
    ]
    test_changes = [
        path
        for path in material
        if "/test/" in path.casefold()
        or "/tests/" in path.casefold()
        or Path(path).name.casefold().startswith("test_")
    ]
    if source_changes and not test_changes:
        risks.append("source-change-without-test-change")
    if repository_test_files == 0:
        risks.append("repository-tests-not-detected")
    if dirty_paths:
        risks.append("working-tree-dirty")
    return tuple(dict.fromkeys(risks))


def _render(bundle: ExecutionBundle) -> str:
    def values(items: tuple[str, ...], fallback: str = "none") -> str:
        return ", ".join(items) if items else fallback

    lines = [
        "# Deterministic execution bundle",
        "",
        f"- Schema: {bundle.schema}",
        f"- Work: {bundle.swarm or '-'} / {bundle.work or '-'}",
        f"- Stage: {bundle.stage or 'unknown'}",
        f"- Next action: {bundle.next_action}",
        f"- Branch: {bundle.branch or 'unknown'}",
        f"- Base: {bundle.base_branch or 'unknown'}",
        f"- HEAD: {bundle.head or 'unknown'}",
        "",
        "## Objective",
        "",
        bundle.objective or "Not available from deterministic Inception.",
        "",
        "## Acceptance criteria",
        "",
        *([f"- {item}" for item in bundle.acceptance_criteria] or ["- none"]),
        "",
        "## Repository facts",
        "",
        f"- Languages: {values(bundle.languages)}",
        f"- Build systems: {values(bundle.build_systems)}",
        f"- Verification commands: {values(bundle.verification_commands)}",
        "",
        "## Changed and dirty paths",
        "",
        *([f"- changed: {item}" for item in bundle.changed_paths] or ["- changed: none"]),
        *([f"- dirty: {item}" for item in bundle.dirty_paths] or ["- dirty: none"]),
        "",
        "## Related paths",
        "",
        *([f"- {item}" for item in bundle.related_paths] or ["- none"]),
        "",
        "## Mechanical risk flags",
        "",
        *([f"- {item}" for item in bundle.risks] or ["- none"]),
        "",
        "## Governance",
        "",
        f"- Human approval required: {bundle.governance.get('human_approval_required', False)}",
        f"- Missing artifacts: {values(tuple(bundle.governance.get('missing_artifacts', ())))}",
        f"- Missing evidence: {values(tuple(bundle.governance.get('missing_evidence', ())))}",
        f"- Missing approvals: {values(tuple(bundle.governance.get('missing_approvals', ())))}",
        f"- Unsatisfied criteria: {values(tuple(bundle.governance.get('unsatisfied_criteria', ())))}",
        "",
        (
            "This bundle is deterministic read-only context. "
            "It does not authorize Construction, approval, review or merge."
        ),
        "",
    ]
    return "\n".join(lines)


def build_execution_bundle(
    root: Path,
    *,
    swarm: str | None = None,
    work: str | None = None,
    persist: bool = True,
) -> ExecutionBundle:
    root = root.expanduser().resolve()
    status = inspect_iteration(root, swarm=swarm, work=work)
    repository = inspect_repository(root)

    objective, acceptance, inception_path = _inception_facts(root, status.work or work)
    changed = _changed_paths(root, status.base_branch)
    dirty = _status_paths(root)
    keywords = _keywords(objective, acceptance)
    related = _related_paths(
        root,
        keywords=keywords,
        changed_paths=changed,
        dirty_paths=dirty,
    )
    risks = _risk_flags(
        changed_paths=changed,
        dirty_paths=dirty,
        repository_test_files=repository.test_files,
    )
    governance = {
        "human_approval_required": bool(status.missing_approvals),
        "missing_artifacts": status.missing_artifacts,
        "missing_evidence": status.missing_evidence,
        "missing_approvals": status.missing_approvals,
        "unsatisfied_criteria": status.unsatisfied_criteria,
        "git_issues": status.git_issues,
        "clarifications": status.clarification_issues,
        "ready_to_transition": status.ready_to_transition,
    }

    bundle = ExecutionBundle(
        schema=SCHEMA,
        swarm=status.swarm or swarm,
        work=status.work or work,
        stage=status.state,
        next_action=status.agent_context()["next_action"],
        branch=status.work_branch or status.current_branch,
        base_branch=status.base_branch,
        head=_head(root),
        objective=objective,
        acceptance_criteria=acceptance,
        changed_paths=changed,
        dirty_paths=dirty,
        related_paths=related,
        languages=repository.languages,
        build_systems=repository.build_systems,
        verification_commands=repository.test_commands,
        risks=risks,
        governance=governance,
        deterministic_inception_path=inception_path,
    )

    if not persist:
        return bundle

    bundle_root = root / ".agora" / "ai-sdlc" / "bundles" / (bundle.work or "unscoped")
    bundle_root.mkdir(parents=True, exist_ok=True)
    json_path = bundle_root / "EXECUTION_BUNDLE.json"
    markdown_path = bundle_root / "EXECUTION_BUNDLE.md"
    persisted = ExecutionBundle(
        **{
            **bundle.snapshot(),
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
        }
    )
    json_path.write_text(json.dumps(persisted.snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render(persisted), encoding="utf-8")
    return persisted


def render_execution_bundle(bundle: ExecutionBundle) -> str:
    return _render(bundle)
