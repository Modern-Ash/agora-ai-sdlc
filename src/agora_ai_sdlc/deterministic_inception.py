"""Deterministic-first Inception planning from explicit issue and repository facts."""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".agora",
    ".venv",
    "node_modules",
    "target",
    "build",
    "dist",
    "__pycache__",
}
LANGUAGE_EXTENSIONS = {
    ".java": "Java",
    ".kt": "Kotlin",
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
}
BUILD_MARKERS = {
    "pom.xml": ("Maven", "mvn test"),
    "build.gradle": ("Gradle", "./gradlew test"),
    "build.gradle.kts": ("Gradle", "./gradlew test"),
    "package.json": ("Node", "npm test"),
    "pnpm-workspace.yaml": ("pnpm", "pnpm test"),
    "pyproject.toml": ("Python", "pytest"),
    "requirements.txt": ("Python", "pytest"),
}
SECTION_ALIASES = {
    "objective": ("objective", "objetivo"),
    "requirements": ("requirements", "requirement", "requisitos", "semantics", "semántica"),
    "acceptance": ("acceptance", "acceptance criteria", "criterios de aceptación", "criterios de aceptacion"),
    "dependencies": ("dependencies", "dependency", "dependencias"),
    "constraints": ("constraints", "constraint", "restricciones"),
}


@dataclass(frozen=True)
class IssueFacts:
    title: str
    objective: str
    requirements: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    dependencies: tuple[str, ...]
    constraints: tuple[str, ...]
    semantic_gaps: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryFacts:
    languages: tuple[str, ...]
    build_systems: tuple[str, ...]
    test_commands: tuple[str, ...]
    top_level: tuple[str, ...]
    files_scanned: int
    test_files: int


@dataclass(frozen=True)
class DeterministicInception:
    output: str
    path: str
    requires_llm: bool
    semantic_gaps: tuple[str, ...]
    issue: IssueFacts
    repository: RepositoryFacts


def _heading_sections(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw in body.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", raw)
        if heading:
            current = heading.group(1).strip().casefold()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(raw)
    return sections


def _section_values(sections: dict[str, list[str]], aliases: tuple[str, ...]) -> tuple[str, ...]:
    lines: list[str] = []
    for heading, body in sections.items():
        normalized = heading.casefold()
        if not any(alias in normalized for alias in aliases):
            continue
        lines.extend(body)

    values: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = re.sub(r"^\[[ xX]\]\s*", "", line)
        if line and not line.startswith("#"):
            values.append(line)
    return tuple(dict.fromkeys(values))


def normalize_issue(payload: dict) -> IssueFacts:
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "")
    sections = _heading_sections(body)

    objective_values = _section_values(sections, SECTION_ALIASES["objective"])
    objective = objective_values[0] if objective_values else title
    requirements = _section_values(sections, SECTION_ALIASES["requirements"])
    acceptance = _section_values(sections, SECTION_ALIASES["acceptance"])
    dependencies = _section_values(sections, SECTION_ALIASES["dependencies"])
    constraints = list(_section_values(sections, SECTION_ALIASES["constraints"]))

    for item in (*requirements, *acceptance):
        lowered = item.casefold()
        if (
            lowered.startswith(("no ", "must not ", "do not ", "without ", "sin "))
            or " no " in lowered
            or "must not" in lowered
        ):
            constraints.append(item)

    criteria = acceptance or requirements
    gaps: list[str] = []
    if not objective.strip():
        gaps.append("objective is not explicit")
    if not criteria:
        gaps.append("acceptance criteria or requirements are not explicit")

    return IssueFacts(
        title=title,
        objective=objective,
        requirements=requirements,
        acceptance_criteria=criteria,
        dependencies=dependencies,
        constraints=tuple(dict.fromkeys(constraints)),
        semantic_gaps=tuple(gaps),
    )


def inspect_repository(root: Path, *, max_files: int = 5000) -> RepositoryFacts:
    root = root.resolve()
    languages: Counter[str] = Counter()
    build_systems: list[str] = []
    test_commands: list[str] = []
    top_level: list[str] = []
    files_scanned = 0
    test_files = 0

    try:
        top_level = sorted(
            item.name for item in root.iterdir() if item.name not in SKIP_DIRS and not item.name.startswith(".")
        )[:40]
    except OSError:
        top_level = []

    for marker, (build_system, test_command) in BUILD_MARKERS.items():
        if (root / marker).is_file():
            build_systems.append(build_system)
            test_commands.append(test_command)

    stop = False
    for current, directories, filenames in os.walk(root):
        directories[:] = [
            directory
            for directory in directories
            if directory not in SKIP_DIRS and not directory.startswith(".")
        ]
        current_path = Path(current)
        for filename in filenames:
            if files_scanned >= max_files:
                stop = True
                break
            path = current_path / filename
            files_scanned += 1
            language = LANGUAGE_EXTENSIONS.get(path.suffix.casefold())
            if language:
                languages[language] += 1
            lowered = path.as_posix().casefold()
            if "/test/" in lowered or "/tests/" in lowered or path.name.casefold().startswith("test_"):
                test_files += 1
        if stop:
            break

    return RepositoryFacts(
        languages=tuple(name for name, _ in languages.most_common()),
        build_systems=tuple(dict.fromkeys(build_systems)),
        test_commands=tuple(dict.fromkeys(test_commands)),
        top_level=tuple(top_level),
        files_scanned=files_scanned,
        test_files=test_files,
    )


def _bullets(values: tuple[str, ...], *, empty: str) -> list[str]:
    if not values:
        return [f"- {empty}"]
    return [f"- {value}" for value in values]


def _trace(criteria: tuple[str, ...]) -> list[str]:
    if not criteria:
        return ["- No explicit criterion was available for deterministic traceability."]
    lines = []
    for index, criterion in enumerate(criteria, start=1):
        lines.append(
            f"- AC-{index:03d}: {criterion} -> plan step implement-{index:02d} -> bolt verify-{index:02d}"
        )
    return lines


def build_deterministic_inception(
    root: Path,
    payload: dict,
    *,
    intent_id: str,
    work_id: str,
    pathway: str,
) -> DeterministicInception:
    issue = normalize_issue(payload)
    repository = inspect_repository(root)
    target = root.resolve() / ".agora" / "ai-sdlc" / "handoffs" / intent_id / "DETERMINISTIC_INCEPTION.md"
    target.parent.mkdir(parents=True, exist_ok=True)

    criteria = issue.acceptance_criteria
    plan_lines = [
        "- scope: execute — lock the explicit issue objective, constraints and acceptance criteria.",
    ]
    for index, criterion in enumerate(criteria, start=1):
        plan_lines.append(f"- implement-{index:02d}: execute — satisfy AC-{index:03d}: {criterion}")
    plan_lines.append("- verify: execute — run targeted verification and collect evidence before review.")

    unit_name = re.sub(r"[^a-z0-9]+", "-", issue.title.casefold()).strip("-") or work_id
    bolt_lines = [
        "- prepare-contract: sequential — confirm scope, repository facts and deterministic acceptance trace.",
    ]
    for index, criterion in enumerate(criteria, start=1):
        bolt_lines.append(
            f"- verify-{index:02d}: sequential — implement and verify AC-{index:03d}; depends on prior accepted scope."
        )
    bolt_lines.append("- final-verification: sequential — run repository checks and collect evidence.")

    facts = [
        f"- Source issue objective: {issue.objective}",
        f"- Pathway: {pathway}",
        f"- Work: {work_id}",
        f"- Repository languages: {', '.join(repository.languages) or 'not detected'}",
        f"- Build systems: {', '.join(repository.build_systems) or 'not detected'}",
        f"- Test files observed: {repository.test_files}",
        f"- Files scanned deterministically: {repository.files_scanned}",
    ]
    if repository.test_commands:
        facts.append(f"- Candidate verification commands: {', '.join(repository.test_commands)}")

    clarifications = (
        _bullets(issue.semantic_gaps, empty="No material clarification detected from the explicit issue.")
        if issue.semantic_gaps
        else ["- No material clarification detected from the explicit issue."]
    )

    risk_lines = [
        *_bullets(issue.constraints, empty="No explicit constraint beyond the source issue was detected."),
        *_bullets(issue.dependencies, empty="No explicit dependency was declared."),
    ]
    if repository.test_files == 0:
        risk_lines.append("- Repository scan did not detect test files; verification coverage requires human review.")

    lines = [
        "## Intent interpretation",
        "",
        issue.objective,
        "",
        "## Material clarifications",
        "",
        *clarifications,
        "",
        "## Level 1 Plan",
        "",
        *plan_lines,
        "",
        "## Proposed Units",
        "",
        f"- UOW candidate: {unit_name} — one cohesive delivery unit for the governed issue.",
        "",
        "## Suggested Bolts",
        "",
        *bolt_lines,
        "",
        "## Acceptance criteria trace",
        "",
        *_trace(criteria),
        "",
        "## Risks, constraints and dependencies",
        "",
        *risk_lines,
        "",
        "## Source facts and proposed decisions",
        "",
        *facts,
        "- Proposed decision: keep this deterministic draft non-authoritative until human review.",
        "",
        "## Files created or modified",
        "",
        f"- {target.relative_to(root.resolve()).as_posix()} (deterministic Inception draft only).",
        "",
        "## Human decision required",
        "",
        (
            "- Resolve the material clarifications above before Construction."
            if issue.semantic_gaps
            else "- Approve, modify or reject this deterministic Inception proposal before Construction."
        ),
        "",
    ]
    output = "\n".join(lines)
    target.write_text(output, encoding="utf-8")
    return DeterministicInception(
        output=output,
        path=str(target),
        requires_llm=bool(issue.semantic_gaps),
        semantic_gaps=issue.semantic_gaps,
        issue=issue,
        repository=repository,
    )
