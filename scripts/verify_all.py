"""Single verification entry point: `uv run python scripts/verify_all.py`.

Runs every phase in order, stops at the first failure and prints the phase and a recovery command.
Needs no network after dependencies are installed and never prints environment variables.
"""

import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\]\(([^)\s]+)\)")
SKIP_DIRS = {".git", ".venv", "dist", "node_modules", ".pytest_cache", "__pycache__"}


class PhaseError(Exception):
    def __init__(self, message: str, recovery: str) -> None:
        super().__init__(message)
        self.recovery = recovery


def run(cmd: list[str], recovery: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise PhaseError((result.stdout + result.stderr).strip() or f"exit {result.returncode}", recovery)
    return result.stdout


def markdown_files(root: Path) -> list[Path]:
    return [p for p in sorted(root.rglob("*.md")) if not SKIP_DIRS & set(p.relative_to(root).parts)]


def check_links(root: Path = ROOT) -> None:
    broken = []
    for path in markdown_files(root):
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            if not (path.parent / target.split("#")[0]).exists():
                broken.append(f"{path.relative_to(root)} -> {target}")
    if broken:
        raise PhaseError("broken local links:\n" + "\n".join(broken), "fix or remove the listed links")


def check_manifest(root: Path = ROOT) -> None:
    sys.path.insert(0, str(root / "src"))
    from agora_ai_sdlc.flavor_manifest import ManifestError, load_manifest

    for path in sorted((root / "src").rglob("flavor.yaml")):
        try:
            load_manifest(path)
        except ManifestError as error:
            raise PhaseError(
                f"{path.relative_to(root)}: {error}", "fix the manifest per docs/reference/flavor-manifest.md"
            ) from error


def check_packs(root: Path = ROOT) -> str:
    methods = root / "registry" / "methods"
    if not methods.is_dir():
        return "no method packs yet (issue #13); nothing to validate"
    agora = ["uv", "run", "agora"]
    for pack in sorted(p for p in methods.iterdir() if p.is_dir()):
        run(agora + ["pack", "validate", str(pack)], f"run: uv run agora pack validate {pack}")
    return "validated"


def check_samples(root: Path = ROOT) -> str:
    samples = [p for p in sorted((root / "samples").glob("*")) if p.name != "README.md"]
    if not samples:
        return "no samples yet (issue #21); nothing to run"
    raise PhaseError("samples exist but no runner is defined", "define a sample runner before adding samples")


def check_package() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run(["uv", "build", "--out-dir", tmp, "--quiet"], "run: uv build")
        wheel = next(Path(tmp).glob("*.whl"))
        venv = Path(tmp) / "venv"
        run(["uv", "venv", "--quiet", str(venv)], "run: uv venv")
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        run(["uv", "pip", "install", "--quiet", "--python", str(python), str(wheel)], "inspect the built wheel")
        # Run outside the repo so the installed wheel, not the source tree, is exercised.
        run(
            [
                str(python),
                "-c",
                "from agora_ai_sdlc.flavor_manifest import *; check_core_compatibility(load_packaged_manifest())",
            ],
            "the built wheel fails to load its manifest; inspect pyproject.toml packaging",
            cwd=Path(tmp),
        )


PHASES: list[tuple[str, Callable[[], object]]] = [
    ("lint", lambda: run(["uv", "run", "ruff", "check", "."], "run: uv run ruff check --fix .")),
    ("format", lambda: run(["uv", "run", "ruff", "format", "--check", "."], "run: uv run ruff format .")),
    ("tests", lambda: run(["uv", "run", "pytest", "-q"], "run: uv run pytest -q -x")),
    ("links", check_links),
    ("manifest", check_manifest),
    ("packs", check_packs),
    ("samples", check_samples),
    ("package", check_package),
]


def main() -> int:
    for name, phase in PHASES:
        print(f"[verify] {name} ...", flush=True)
        try:
            note = phase()
        except PhaseError as error:
            print(f"[verify] FAILED phase: {name}\n{error}\nrecovery: {error.recovery}", file=sys.stderr)
            return 1
        suffix = f" ({note})" if name in ("packs", "samples") and isinstance(note, str) else ""
        print(f"[verify] {name} ok{suffix}")
    print("[verify] all phases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
