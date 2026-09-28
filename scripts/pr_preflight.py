"""Mandatory pull-request preflight.

Run the same full repository verification used by CI and, when available,
exercise the installed project against the newest supported Agora Core.

This script is intentionally the single agent/human entry point before opening
or updating a pull request. CI should confirm this result, not discover basic
format/test/compatibility failures for the first time.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWEST_SUPPORTED_CORE = os.environ.get("AGORA_PREFLIGHT_CORE", "0.9.1")


def run(command: list[str], *, env: dict[str, str] | None = None) -> int:
    print(f"[pr-preflight] $ {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


def main() -> int:
    if run([sys.executable, "scripts/verify_all.py"]) != 0:
        print("[pr-preflight] repository verification failed", file=sys.stderr)
        return 1

    # Core compatibility needs an isolated environment because the normal uv
    # lock intentionally pins the repository's baseline supported Core.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "venv"
        if run(["uv", "venv", "--quiet", "--python", "3.13", str(venv)]) != 0:
            return 1
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        packages = [
            f"agora-framework=={NEWEST_SUPPORTED_CORE}",
            "pytest",
            "packaging>=24",
            "pyyaml",
            "jsonschema",
        ]
        if run(["uv", "pip", "install", "--quiet", "--python", str(python), *packages]) != 0:
            print(
                "[pr-preflight] newest-Core dependencies unavailable; "
                "set AGORA_PREFLIGHT_CORE or ensure dependency access",
                file=sys.stderr,
            )
            return 1
        if run(["uv", "pip", "install", "--quiet", "--python", str(python), "--no-deps", "-e", "."]) != 0:
            return 1
        if run([str(python), "-m", "pytest", "-q"]) != 0:
            print(
                f"[pr-preflight] Core {NEWEST_SUPPORTED_CORE} compatibility failed",
                file=sys.stderr,
            )
            return 1

    print("[pr-preflight] all PR checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
