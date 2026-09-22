"""Portable, provider-neutral Inception handoff generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agora_ai_sdlc.guided import skill_path


@dataclass(frozen=True)
class InceptionHandoff:
    intent_id: str
    issue_url: str
    runtime_id: str
    runtime_name: str
    path: str
    skill: str


def write_inception_handoff(
    root: Path,
    *,
    intent_id: str,
    issue_url: str,
    issue_title: str,
    runtime_id: str,
    runtime_name: str,
) -> InceptionHandoff:
    """Persist the portable Start -> Inception contract for any compatible agent."""

    target = root / ".agora" / "ai-sdlc" / "handoffs" / intent_id / "INCEPTION_HANDOFF.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    skill = skill_path()

    target.write_text(
        "\n".join(
            [
                "---",
                'schema: "agora-ai-sdlc/inception-handoff/v1"',
                f'intent: "{intent_id}"',
                f'issue: "{issue_url}"',
                f'runtime: "{runtime_id}"',
                'status: "prepared"',
                "---",
                "",
                f"# Inception handoff — {intent_id}",
                "",
                "## Objective",
                "",
                issue_title,
                "",
                "## Authority",
                "",
                "Follow the installed Agora AI-SDLC guided skill. Agora Core remains lifecycle authority.",
                f"Skill: `{skill}`",
                f"Load only the Inception resource: `{skill.parent / 'references' / 'inception.md'}`.",
                "Human observation logs are not agent context; do not load or replay them.",
                "",
                "## Required inputs",
                "",
                f"- Durable Intent: `.agora/intents/{intent_id}/INTENT.md`",
                f"- Source issue: {issue_url}",
                "- Repository AGENTS.md and bounded product/architecture context referenced by the issue",
                "",
                "## Required Inception output contract",
                "",
                "Return and, where existing AI-SDLC contracts permit, persist all of:",
                "",
                "1. Intent interpretation.",
                "2. Material clarifications requiring human decision.",
                "3. Level 1 Plan.",
                "4. Cohesive Units.",
                "5. Suggested Bolts.",
                "6. Acceptance criteria traced to the source issue.",
                "7. Risks, constraints and dependencies.",
                "8. Explicit distinction between source facts and proposed product decisions.",
                "9. Files created or modified.",
                "10. Human decision required to continue.",
                "",
                "## Stop conditions",
                "",
                "- Do not enter Construction.",
                "- Do not implement product code.",
                "- Do not fabricate or infer human approval.",
                "- Stop on material ambiguity and ask one bounded decision question.",
                "- Stop after presenting the complete Inception proposal for human review.",
                "",
                "## Runtime",
                "",
                f"Selected executor interface: {runtime_name} (`{runtime_id}`).",
                "Runtime selection changes who executes this handoff, never the method semantics.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return InceptionHandoff(
        intent_id=intent_id,
        issue_url=issue_url,
        runtime_id=runtime_id,
        runtime_name=runtime_name,
        path=str(target),
        skill=str(skill),
    )
