"""Guard the public Agora Flow surface from leaking low-level Core CLI instructions."""

from pathlib import Path

PUBLIC_SURFACES = (
    "README.md",
    "skills/agora-ai-sdlc-guided/SKILL.md",
    "skills/agora-ai-sdlc-guided/references/construction.md",
    "skills/agora-ai-sdlc-guided/references/inception.md",
    "skills/agora-ai-sdlc-guided/references/delivery.md",
)

# Expert/debug prose may mention Core conceptually. The public happy path must not
# contain executable low-level Core CLI examples/instructions.
FORBIDDEN = (
    "agora work ",
    "agora approval ",
    "agora artifact ",
    "agora evidence ",
    "agora criterion ",
    "agora session ",
)


def test_public_flow_surfaces_do_not_require_core_cli():
    root = Path(__file__).resolve().parents[1]
    leaks = []
    for relative in PUBLIC_SURFACES:
        path = root / relative
        text = path.read_text(encoding="utf-8").casefold()
        for command in FORBIDDEN:
            if command in text:
                leaks.append(f"{relative}: {command.strip()}")

    assert leaks == [], "normal Flow surfaces leaked Core CLI plumbing: " + ", ".join(leaks)
