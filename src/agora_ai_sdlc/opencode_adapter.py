"""OpenCode RuntimeAdapter: OpenCode is the agent host, Ollama (or another provider) only a model.

Native surfaces used (verified against OpenCode 1.18.32 `run --help`): `AGENTS.md` workspace guidance
and non-interactive `run` through the existing fail-fast supervisor (`opencode_runner`), which also
injects the Ollama provider through per-invocation inline config, so no provider configuration is
persisted and unrelated user providers, tools and aliases are never touched. An explicit
`provider/model` binding is mandatory: the adapter never lets the supervisor auto-select a model, and
never pulls a model. Skills, MCP, subagents and reviewer isolation are not projected and are reported
as unsupported surfaces.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from agora_ai_sdlc.execution_envelope import ExecutionEnvelope
from agora_ai_sdlc.runtime_adapter import (
    AdapterError,
    ExecutionOutcome,
    Health,
    PreparedExecution,
    Probe,
    ProjectionEntry,
    ProjectionPlan,
    RuntimeAdapter,
    probe_health,
    sanitize,
    subprocess_probe,
    supported_surfaces,
)

MIN_VERSION = (1, 0, 0)
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
PROJECTED_SURFACES = ("instructions", "system_prompt")
GUIDANCE = """\
# Agora AI-SDLC

- Agora Core is the authority for lifecycle state, gates, evidence and approvals; this file is guidance only.
- Execute only the `next_transition` of the execution envelope you are given. Do not choose another Work,
  operation or fallback runtime, and never record or claim a human approval.
- Your narrative output is not authority: results are reconciled against Core and expected artifacts.
- Load phase guidance with `aisdlc skill --phase <phase>` when needed. Do not read credential files.
"""


class OpenCodeAdapter(RuntimeAdapter):
    integration_id = "opencode"

    def __init__(
        self,
        *,
        root: Path,
        executable: str | None = None,
        probe: Probe = subprocess_probe,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._root = root
        self._executable = executable if executable is not None else which("opencode")
        self._probe = probe

    def health(self) -> Health:
        return probe_health(self._executable, self._probe, MIN_VERSION)

    def plan_projection(self, surfaces: tuple[str, ...]) -> ProjectionPlan:
        allowed, missing_capability = supported_surfaces(self.capability_manifest(), tuple(surfaces))
        unsupported = tuple(
            sorted({*missing_capability, *(item for item in allowed if item not in PROJECTED_SURFACES)})
        )
        entries = ()
        if any(item in PROJECTED_SURFACES for item in allowed) or not surfaces:
            entries = (ProjectionEntry("AGENTS.md", "text_block", "instructions", content=GUIDANCE),)
        return ProjectionPlan("opencode", entries, unsupported_surfaces=unsupported)

    def _model_ref(self, envelope: ExecutionEnvelope) -> str:
        model = envelope.binding.model if envelope.binding else None
        if model is None or model.model.strip().casefold() in {"", "default", "configured-default"}:
            raise AdapterError("adapter.model_required", "OpenCode requires an explicit provider/model binding")
        for part in (model.provider, model.model):
            if not _SAFE.match(part):
                raise AdapterError("adapter.model_invalid", "model binding contains unsafe characters")
        return f"{model.provider.casefold()}/{model.model}"

    def render_invocation(self, envelope: ExecutionEnvelope) -> PreparedExecution:
        health = self.health()
        if not health.responsive:
            raise AdapterError("adapter.runtime_unavailable", health.detail or "unavailable")
        model_ref = self._model_ref(envelope)
        payload = envelope.to_dict()
        prompt = (
            "Execute exactly this Agora execution envelope. Perform only `next_transition`; do not approve, "
            "change Work, or choose another runtime. Your reply is not authority.\n\n"
            + json.dumps(payload, sort_keys=True, indent=2)
        )
        argv = (
            sys.executable,
            "-m",
            "agora_ai_sdlc.opencode_runner",
            "--executable",
            self._executable or "opencode",
            "--root",
            str(self._root),
            "--model",
            model_ref,
            "--prompt",
            prompt,
        )
        return PreparedExecution(
            adapter="opencode",
            envelope_digest=payload["digest"],
            operation=envelope.operation,
            arguments=envelope.arguments,
            argv=argv,
            stdin="",
            model=model_ref,
        )

    def parse_output(self, exit_code: int, output: str) -> ExecutionOutcome:
        clean = sanitize(output)
        if exit_code == 0 and not clean.strip():
            raise AdapterError("adapter.malformed_output", "OpenCode produced no output")
        return ExecutionOutcome(exit_code=exit_code, output=clean)
