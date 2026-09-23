"""Deterministic validation of human-reviewable Inception output."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

REQUIRED_SECTIONS = (
    "Intent interpretation",
    "Material clarifications",
    "Level 1 Plan",
    "Proposed Units",
    "Suggested Bolts",
    "Acceptance criteria trace",
    "Risks, constraints and dependencies",
    "Source facts and proposed decisions",
    "Files created or modified",
    "Human decision required",
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "implement",
    "implementation",
    "of",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class InceptionValidation:
    valid: bool
    violations: tuple[str, ...]


def _section_map(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^#{2,6}\s+(.+?)\s*$", line)
        if match:
            current = match.group(1).strip().casefold()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def _objective(handoff_path: Path) -> str:
    body = handoff_path.read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^## Objective\s*$\n+(.*?)(?=^##\s+|\Z)",
        body,
    )
    return match.group(1).strip() if match else ""


def _objective_terms(objective: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", objective.casefold())
        if token not in STOP_WORDS
    }


def validate_inception_output(output: str, handoff_path: Path) -> InceptionValidation:
    """Fail closed unless output follows the portable Inception presentation contract."""

    violations: list[str] = []
    sections = _section_map(output)

    for heading in REQUIRED_SECTIONS:
        content = sections.get(heading.casefold())
        if content is None:
            violations.append(f"missing section: {heading}")
        elif not content.strip():
            violations.append(f"empty section: {heading}")

    objective = _objective(handoff_path)
    terms = _objective_terms(objective)
    if terms:
        normalized = output.casefold()
        matched = {term for term in terms if re.search(rf"\b{re.escape(term)}\b", normalized)}
        required = min(2, max(1, math.ceil(len(terms) * 0.3)))
        if len(matched) < required:
            violations.append(
                "output is not grounded in the handoff objective "
                f"(matched {len(matched)}/{required} required objective terms)"
            )

    return InceptionValidation(valid=not violations, violations=tuple(violations))
