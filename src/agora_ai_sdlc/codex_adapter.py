"""Codex RuntimeAdapter: projects Agora contracts into Codex's native surfaces.

Native surfaces used (verified against codex-cli 0.156.1 `exec --help`): `AGENTS.md` workspace
guidance, `codex exec` with the prompt on stdin, `--ephemeral`, `--color never`, `--sandbox`
(never `danger-full-access`) and `--model`. Skills, MCP, subagents and a reviewer boundary are not
projected and are reported as unsupported surfaces. The default OpenAI provider is the only
supported model provider.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable

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

MIN_VERSION = (0, 156, 0)
DEFAULT_MODEL_SENTINELS = frozenset({"", "default", "configured-default"})
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
PROJECTED_SURFACES = ("instructions", "system_prompt")
GUIDANCE = """\
# Agora AI-SDLC

- Agora Core is the authority for lifecycle state, gates, evidence and approvals; this file is guidance only.
- Execute only the `next_transition` of the execution envelope you are given. Do not choose another Work,
  operation or fallback runtime, and never record or claim a human approval.
- Your narrative output is not authority: results are reconciled against Core and expected artifacts.
- Load phase guidance with `aisdlc skill --phase <phase>` when needed. Do not read credential files.
"""


class CodexAdapter(RuntimeAdapter):
    integration_id = "codex"

    def __init__(
        self,
        *,
        executable: str | None = None,
        probe: Probe = subprocess_probe,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._executable = executable if executable is not None else which("codex")
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
        return ProjectionPlan("codex", entries, unsupported_surfaces=unsupported)

    def _model_flags(self, envelope: ExecutionEnvelope) -> tuple[str, ...]:
        model = envelope.binding.model if envelope.binding else None
        if model is None or model.model.strip().casefold() in DEFAULT_MODEL_SENTINELS:
            return ()  # native default; a paid model is never picked silently
        if model.provider.casefold() != "openai":
            raise AdapterError("adapter.model_unsupported", f"Codex adapter cannot serve provider {model.provider!r}")
        if not _MODEL.match(model.model):
            raise AdapterError("adapter.model_invalid", "model assignment is not a safe Codex model id")
        return ("--model", model.model)

    def render_invocation(self, envelope: ExecutionEnvelope) -> PreparedExecution:
        health = self.health()
        if not health.responsive:
            raise AdapterError("adapter.runtime_unavailable", health.detail or "unavailable")
        capabilities = set(envelope.requirements.get("required_capabilities", ()))
        sandbox = "workspace-write" if "workspace.write" in capabilities else "read-only"
        model_flags = self._model_flags(envelope)
        payload = envelope.to_dict()
        prompt = (
            "Execute exactly this Agora execution envelope. Perform only `next_transition`; do not approve, "
            "change Work, or choose another runtime. Your reply is not authority.\n\n"
            + json.dumps(payload, sort_keys=True, indent=2)
        )
        argv = (
            self._executable or "codex",
            "exec",
            "--ephemeral",
            "--color",
            "never",
            "--sandbox",
            sandbox,
            *model_flags,
            "-",
        )
        return PreparedExecution(
            adapter="codex",
            envelope_digest=payload["digest"],
            operation=envelope.operation,
            arguments=envelope.arguments,
            argv=argv,
            stdin=prompt,
            model=model_flags[1] if model_flags else None,
        )

    def parse_output(self, exit_code: int, output: str) -> ExecutionOutcome:
        clean = sanitize(output)
        if exit_code == 0 and not clean.strip():
            raise AdapterError("adapter.malformed_output", "Codex produced no output")
        return ExecutionOutcome(exit_code=exit_code, output=clean)
