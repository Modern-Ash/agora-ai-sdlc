"""Neutral subprocess entrypoint used by Agora Core Sessions to invoke RuntimeAdapters."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.execution_envelope import snapshot_from_workspace, verify_integrity
from agora_ai_sdlc.execution_requirements import requirements_from_dict
from agora_ai_sdlc.iteration_status import inspect_iteration
from agora_ai_sdlc.runtime_adapter import AdapterError


def _run_native(argv: tuple[str, ...], stdin: str, *, root: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(argv),
            cwd=root,
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return 127, f"{type(error).__name__}: {error}"
    if result.returncode == 0:
        return result.returncode, result.stdout
    diagnostic = result.stderr.strip() or result.stdout
    return result.returncode, diagnostic


def run(root: Path, envelope_path: Path) -> int:
    root = root.resolve()
    path = envelope_path if envelope_path.is_absolute() else root / envelope_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        envelope = verify_integrity(payload)
        if envelope.binding is None:
            raise AdapterError("adapter.not_executable", "execution envelope has no runtime binding")

        requirements = requirements_from_dict(envelope.requirements)
        workspace = AgoraWorkspace(cwd=root)
        status = inspect_iteration(root, swarm=envelope.swarm, work=envelope.work)
        snapshot = snapshot_from_workspace(workspace, status)
        adapter = default_registry(root).get(envelope.binding.agent)
        prepared = adapter.prepare_execution(payload, current=(snapshot, requirements))
        outcome = adapter.launch(prepared, lambda argv, stdin: _run_native(argv, stdin, root=root))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2

    if outcome.output:
        stream = sys.stdout if outcome.exit_code == 0 else sys.stderr
        print(outcome.output, file=stream)
    return outcome.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute one validated Agora RuntimeAdapter envelope")
    parser.add_argument("--root", required=True)
    parser.add_argument("--envelope", required=True)
    args = parser.parse_args(argv)
    return run(Path(args.root), Path(args.envelope))


if __name__ == "__main__":
    raise SystemExit(main())
