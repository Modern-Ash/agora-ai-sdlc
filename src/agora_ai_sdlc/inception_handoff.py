"""Portable, provider-neutral Inception handoff generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InceptionHandoff:
    intent_id: str
    issue_url: str
    runtime_id: str
    runtime_name: str
    swarm_id: str
    work_id: str
    branch: str | None
    base_branch: str | None
    pathway: str
    project_root: str
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
    swarm_id: str,
    work_id: str,
    branch: str | None,
    base_branch: str | None,
    pathway: str,
    deterministic_draft: str | None = None,
    semantic_gaps: tuple[str, ...] = (),
) -> InceptionHandoff:
    """Persist the portable Start -> Inception contract for any compatible agent."""

    root = root.resolve()
    target = root / ".agora" / "ai-sdlc" / "handoffs" / intent_id / "INCEPTION_HANDOFF.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    skill = root / ".agora" / "skills" / "agora-ai-sdlc-guided" / "SKILL.md"
    skill_reference = skill.relative_to(root).as_posix()
    inception_reference = (skill.parent / "references" / "inception.md").relative_to(root).as_posix()

    target.write_text(
        "\n".join(
            [
                "---",
                'schema: "agora-ai-sdlc/inception-handoff/v1"',
                f'intent: "{intent_id}"',
                f'issue: "{issue_url}"',
                f'runtime: "{runtime_id}"',
                f'swarm: "{swarm_id}"',
                f'work: "{work_id}"',
                f'branch: "{branch or ""}"',
                f'base-branch: "{base_branch or ""}"',
                f'pathway: "{pathway}"',
                f'project-root: "{root}"',
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
                f"Skill: `{skill_reference}`",
                f"Load only the Inception resource: `{inception_reference}`.",
                "Human observation logs are not agent context; do not load or replay them.",
                "",
                "## Required inputs",
                "",
                f"- Project root: `{root}`",
                "- Executor must verify its current working directory resolves exactly to this project root before changing files.",
                f"- Durable Intent: `.agora/intents/{intent_id}/INTENT.md`",
                f"- Governed Work: `{swarm_id}/{work_id}`",
                f"- Work branch: `{branch or 'unbound'}` (base: `{base_branch or 'unknown'}`)",
                f"- Adaptive pathway: `{pathway}`",
                f"- Source issue: {issue_url}",
                "- Repository AGENTS.md and bounded product/architecture context referenced by the issue",
                "",
                *(
                    [
                        "## Deterministic draft",
                        "",
                        f"- Draft: `{deterministic_draft}`",
                        "- Treat this Python-generated draft as the baseline; do not re-explore the repository or recreate facts already present there.",
                        "- Only resolve the semantic gaps listed below and preserve deterministic facts unless authoritative evidence contradicts them.",
                        *([f"- Semantic gap: {gap}" for gap in semantic_gaps] or ["- Semantic gap: none"]),
                        "",
                    ]
                    if deterministic_draft is not None
                    else []
                ),
                "## Required Inception output contract",
                "",
                "Return and, where existing AI-SDLC contracts permit, persist all of the following.",
                "The final response must use these exact Markdown H2 headings:",
                "",
                "1. `## Intent interpretation`",
                "2. `## Material clarifications`",
                "3. `## Level 1 Plan`",
                "4. `## User Stories`",
                "5. `## Non-functional requirements`",
                "6. `## Measurement Criteria`",
                "7. `## Proposed Units` (cohesive Units where decomposition adds execution value)",
                "8. `## Suggested Bolts`",
                "9. `## Acceptance criteria trace`",
                "10. `## Risk Register`",
                "11. `## Risks, constraints and dependencies`",
                "12. `## Source facts and proposed decisions`",
                "13. `## Files created or modified`",
                "14. `## Human decision required`",
                "",
                "Every section must contain substantive content and the proposal must remain grounded in the Objective above.",
                "PRFAQ is optional: propose it only when a customer/business narrative materially improves alignment.",
                "",
                "## Stop conditions",
                "",
                "- Do not enter Construction.",
                "- Do not implement product code.",
                "- Do not fabricate or infer human approval.",
                "- Do not ask the human to reconfirm a decision already fixed by the source issue or referenced authoritative docs.",
                "- Stop on unresolved material ambiguity and ask one bounded decision question.",
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
        swarm_id=swarm_id,
        work_id=work_id,
        branch=branch,
        base_branch=base_branch,
        pathway=pathway,
        project_root=str(root),
        path=str(target),
        skill=str(skill),
    )
