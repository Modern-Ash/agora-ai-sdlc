"""Fast local verification for Git pre-commit.

This is intentionally a subset of scripts/verify_all.py:
- syntax/importability at the Python parser level
- Ruff lint
- Ruff format check
- staged whitespace errors

It is fast enough to run on every commit and catches the classes of failures
that should never reach CI.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(name: str, command: list[str], recovery: str) -> bool:
    print(f"[pre-commit] {name} ...", flush=True)
    result = subprocess.run(command, cwd=ROOT, text=True, check=False)
    if result.returncode != 0:
        print(f"[pre-commit] FAILED: {name}", file=sys.stderr)
        print(f"[pre-commit] recovery: {recovery}", file=sys.stderr)
        return False
    print(f"[pre-commit] {name} ok")
    return True


def main() -> int:
    phases = (
        (
            "syntax",
            [sys.executable, "-m", "compileall", "-q", "src", "tests", "scripts"],
            "fix the Python syntax error reported above",
        ),
        (
            "lint",
            ["uv", "run", "ruff", "check", "."],
            "uv run ruff check --fix .",
        ),
        (
            "format",
            ["uv", "run", "ruff", "format", "--check", "."],
            "uv run ruff format .",
        ),
        (
            "staged-diff",
            ["git", "diff", "--cached", "--check"],
            "fix staged whitespace/conflict-marker errors and stage the result again",
        ),
    )
    for name, command, recovery in phases:
        if not run(name, command, recovery):
            return 1
    print("[pre-commit] all fast checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
