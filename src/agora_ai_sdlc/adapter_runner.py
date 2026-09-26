"""Execute one validated ExecutionEnvelope through its registered RuntimeAdapter."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.execution_envelope import verify_integrity
from agora_ai_sdlc.runtime_adapter import AdapterError


def _run(argv: tuple[str, ...], stdin: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(argv),
            input=stdin,
            cwd=_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return 127, error.__class__.__name__
    output = result.stdout or ""
    if result.stderr:
        output = output + ("\n" if output else "") + result.stderr
    return result.returncode, output


_ROOT = Path(".")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--envelope", required=True)
    args = parser.parse_args(argv)

    global _ROOT
    _ROOT = Path(args.root).resolve()
    try:
        payload = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
        envelope = verify_integrity(payload)
        if envelope.binding is None:
            raise AdapterError("adapter.not_executable", "execution envelope has no runtime binding")
        adapter = default_registry(_ROOT).get(envelope.binding.agent)
        prepared = adapter.prepare_execution(payload)
        outcome = adapter.launch(prepared, _run)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2

    if outcome.output:
        print(outcome.output)
    return int(outcome.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
