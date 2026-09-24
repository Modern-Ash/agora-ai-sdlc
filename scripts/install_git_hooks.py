"""Install repository-owned Git pre-commit and pre-push hooks.

The generated hooks live in Git's actual hooks directory, so this works for
normal clones and linked worktrees. Existing unmanaged hooks are never
overwritten.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = "# managed-by: agora-ai-sdlc"

HOOKS = {
    "pre-commit": """#!/bin/sh
# managed-by: agora-ai-sdlc
set -eu
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
exec uv run python scripts/verify_commit.py
""",
    "pre-push": """#!/bin/sh
# managed-by: agora-ai-sdlc
set -eu
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
exec uv run python scripts/verify_all.py
""",
}


def hooks_dir() -> Path:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--git-path", "hooks"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError((result.stderr or "cannot resolve Git hooks directory").strip())
    path = Path(result.stdout.strip())
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def install_hook(directory: Path, name: str, content: str) -> None:
    target = directory / name
    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="replace")
        if MARKER not in existing:
            raise RuntimeError(
                f"Refusing to overwrite unmanaged Git hook: {target}. "
                "Merge it manually with the Agora AI-SDLC hook."
            )

    target.write_text(content, encoding="utf-8")
    mode = target.stat().st_mode
    target.chmod(mode | 0o111)
    print(f"installed {name}: {target}")


def main() -> int:
    try:
        directory = hooks_dir()
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in HOOKS.items():
            install_hook(directory, name, content)
    except (OSError, RuntimeError) as error:
        print(f"hook installation failed: {error}", file=sys.stderr)
        return 1

    print("Git hooks installed.")
    print("pre-commit: syntax + Ruff lint + Ruff format + staged diff")
    print("pre-push: full scripts/verify_all.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
