"""Execute one validated ExecutionEnvelope through its registered RuntimeAdapter."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.execution_economics import EconomicsEvent, core_usage_snapshot, record_event
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


def _record(
    envelope,
    event: str,
    *,
    exit_code: int | None = None,
    reason: str | None = None,
    measurement: dict | None = None,
) -> None:
    if envelope.binding is None:
        return
    context = dict(envelope.context or {})
    routing = context.get("routing") if isinstance(context.get("routing"), dict) else {}
    tier = routing.get("tier") if isinstance(routing.get("tier"), str) else "override"
    purpose = context.get("purpose") if isinstance(context.get("purpose"), str) else None
    model = envelope.binding.model.model if envelope.binding.model is not None else None
    try:
        workspace = AgoraWorkspace(cwd=_ROOT)
        usage = core_usage_snapshot(workspace, envelope.swarm, envelope.work)
        record_event(
            _ROOT,
            EconomicsEvent(
                event,
                envelope.work,
                tier,
                envelope.binding.agent.id,
                model,
                purpose=purpose,
                reason=reason,
                exit_code=exit_code,
                core_usage=usage,
                measurement=measurement,
            ),
        )
    except (OSError, RuntimeError, ValueError):
        pass


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
        _record(envelope, "attempt")
        outcome = adapter.launch(prepared, _run)
        structured = dict(outcome.structured or {})
        provider_usage = structured.get("usage")
        measurement = (
            {"provider_usage": dict(provider_usage)}
            if isinstance(provider_usage, dict) and provider_usage.get("basis") == "provider_reported_tokens"
            else None
        )
        _record(
            envelope,
            "success" if outcome.exit_code == 0 else "failure",
            exit_code=int(outcome.exit_code),
            reason=None if outcome.exit_code == 0 else "runtime-exit",
            measurement=measurement,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2

    if outcome.output:
        print(outcome.output)
    return int(outcome.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
