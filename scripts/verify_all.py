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
    """Install each Method Pack into a throwaway Agora project and run `agora validate`."""
    methods = root / "registry" / "methods"
    packs = sorted(p for p in methods.iterdir() if p.is_dir()) if methods.is_dir() else []
    if not packs:
        return "no method packs; nothing to validate"
    agora = [sys.executable, "-m", "agora"]
    for pack in packs:
        with tempfile.TemporaryDirectory() as tmp:
            recovery = f"reproduce: agora method install --source {pack} --scope project, then agora validate"
            run(["git", "init", "--quiet", tmp], "install git")
            run([*agora, "init", "--path", tmp], recovery, cwd=Path(tmp))
            run([*agora, "method", "install", "--source", str(pack), "--scope", "project"], recovery, cwd=Path(tmp))
            run([*agora, "validate"], recovery, cwd=Path(tmp))
    return f"validated {len(packs)} pack(s)"


def check_samples(root: Path = ROOT) -> str:
    """Run every sample under samples/ via the CLI and assert its JSON summary."""
    import json

    samples = [p for p in sorted((root / "samples").glob("*")) if p.is_dir()]
    if not samples:
        return "no samples; nothing to run"
    for sample in samples:
        out = run(
            ["uv", "run", "agora-ai-sdlc", "run-sample", sample.name],
            f"reproduce: uv run agora-ai-sdlc run-sample {sample.name}",
            cwd=root,
        )
        summary = json.loads(out)
        if summary.get("final_state") != "completed" or summary.get("validate") != "ok":
            raise PhaseError(
                f"sample {sample.name} ended in {summary.get('final_state')!r}", "inspect the sample summary"
            )
    return f"ran {len(samples)} sample(s)"


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
                (
                    "from agora_ai_sdlc.depth_profiles import asset_root; "
                    "from agora_ai_sdlc.flavor_manifest import *; "
                    "check_core_compatibility(load_packaged_manifest()); "
                    "assert (asset_root('contracts') / 'studio' / "
                    "'ai-sdlc-projection-v1.schema.json').is_file()"
                ),
            ],
            "the built wheel fails to load its manifest; inspect pyproject.toml packaging",
            cwd=Path(tmp),
        )
        # The bundled sample must also pass from the installed wheel.
        out = run([str(venv / ("Scripts" if sys.platform == "win32" else "bin") / "agora-ai-sdlc"), "run-sample", "new-product"],
                  "the built wheel fails to run the bundled sample", cwd=Path(tmp))  # fmt: skip
        if '"final_state": "completed"' not in out:
            raise PhaseError("wheel-installed sample did not complete", "inspect the bundled sample")


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
        suffix = f" ({note})" if isinstance(note, str) and note else ""
        print(f"[verify] {name} ok{suffix}")
    print("[verify] all phases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
