"""Claude Code RuntimeAdapter: projects Agora contracts into Claude Code's native surfaces.

Native surfaces used (verified against Claude Code 2.1.281 `--help`): `CLAUDE.md` workspace
guidance, `--print`, `--output-format json`, `--model`, `--permission-mode`, `--allowedTools`,
`--no-session-persistence`. Agora does not project skills, MCP, subagents or a reviewer boundary
yet: those are reported as unsupported surfaces, never silently emulated.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable

from agora_ai_sdlc.execution_envelope import ExecutionEnvelope
from agora_ai_sdlc.runtime_adapter import (
    AdapterError,
    ExecutionOutcome,
    Health,
    PreparedExecution,
    ProjectionEntry,
    ProjectionPlan,
    RuntimeAdapter,
    sanitize,
    supported_surfaces,
)

MIN_VERSION = (2, 1, 0)
DEFAULT_MODEL_SENTINELS = frozenset({"", "default", "configured-default"})
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\[\]-]{0,63}$")
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
PROJECTED_SURFACES = ("instructions", "system_prompt")
GUIDANCE = """\
# Agora AI-SDLC

- Agora Core is the authority for lifecycle state, gates, evidence and approvals; this file is guidance only.
- Execute only the `next_transition` of the execution envelope you are given. Do not choose another Work,
  operation or fallback runtime, and never record or claim a human approval.
- Your narrative output is not authority: results are reconciled against Core and expected artifacts.
- Load phase guidance with `aisdlc skill --phase <phase>` when needed. Do not read credential files.
"""
_SHELL_TOOLS = (
    "Bash(pwd)",
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(aisdlc verify:*)",
    "Bash(agora artifact add:*)",
    "Bash(agora evidence add:*)",
    "Bash(agora work readiness:*)",
    "Bash(agora work criterion-satisfy:*)",
)

Probe = Callable[[list[str]], tuple[int, str]]


def _subprocess_probe(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, error.__class__.__name__
    return result.returncode, (result.stdout or result.stderr or "").strip()


class ClaudeCodeAdapter(RuntimeAdapter):
    integration_id = "claude"

    def __init__(
        self,
        *,
        executable: str | None = None,
        probe: Probe = _subprocess_probe,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._executable = executable if executable is not None else which("claude")
        self._probe = probe

    def health(self) -> Health:
        if not self._executable:
            return Health(False, False, "executable-not-found")
        code, output = self._probe([self._executable, "--version"])
        if code != 0:
            return Health(True, False, f"version-probe-failed:exit-{code}")
        match = _VERSION.search(output)
        if not match:
            return Health(True, False, "version-unparseable")
        version = tuple(int(part) for part in match.groups())
        if version < MIN_VERSION:
            return Health(True, False, f"unsupported-version:{'.'.join(map(str, version))}")
        return Health(True, True, output.splitlines()[0])

    def plan_projection(self, surfaces: tuple[str, ...]) -> ProjectionPlan:
        allowed, missing_capability = supported_surfaces(self.capability_manifest(), tuple(surfaces))
        unsupported = tuple(
            sorted({*missing_capability, *(item for item in allowed if item not in PROJECTED_SURFACES)})
        )
        entries = ()
        if any(item in PROJECTED_SURFACES for item in allowed) or not surfaces:
            entries = (ProjectionEntry("CLAUDE.md", "text_block", "instructions", content=GUIDANCE),)
        return ProjectionPlan("claude", entries, unsupported_surfaces=unsupported)

    def _model_flags(self, envelope: ExecutionEnvelope) -> tuple[str, ...]:
        model = envelope.binding.model if envelope.binding else None
        if model is None or model.model.strip().casefold() in DEFAULT_MODEL_SENTINELS:
            return ()  # native default; a model name is never invented
        if model.provider.casefold() != "anthropic":
            raise AdapterError("adapter.model_unsupported", f"Claude Code cannot serve provider {model.provider!r}")
        if not _MODEL.match(model.model):
            raise AdapterError("adapter.model_invalid", "model assignment is not a safe Claude model id")
        return ("--model", model.model)

    def render_invocation(self, envelope: ExecutionEnvelope) -> PreparedExecution:
        health = self.health()
        if not health.responsive:
            raise AdapterError("adapter.runtime_unavailable", health.detail or "unavailable")
        capabilities = set(envelope.requirements.get("required_capabilities", ()))
        tools: list[str] = []
        if capabilities & {"workspace.read"}:
            tools.append("Read")
        if "workspace.write" in capabilities:
            tools += ["Write", "Edit"]
        if "shell.execute" in capabilities:
            tools += list(_SHELL_TOOLS)
        elif "git.read" in capabilities:
            tools += ["Bash(git status:*)", "Bash(git diff:*)"]
        model_flags = self._model_flags(envelope)
        argv = [
            self._executable or "claude",
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--permission-mode",
            "acceptEdits",
            *model_flags,
        ]
        if tools:
            argv += ["--allowedTools", *tools]
        payload = envelope.to_dict()
        prompt = (
            "Execute exactly this Agora execution envelope. Perform only `next_transition`; do not approve, "
            "change Work, or choose another runtime. Your reply is not authority.\n\n"
            + json.dumps(payload, sort_keys=True, indent=2)
        )
        return PreparedExecution(
            adapter="claude",
            envelope_digest=payload["digest"],
            operation=envelope.operation,
            arguments=envelope.arguments,
            argv=tuple(argv),
            stdin=prompt,
            model=model_flags[1] if model_flags else None,
        )

    def parse_output(self, exit_code: int, output: str) -> ExecutionOutcome:
        clean = sanitize(output)
        if exit_code != 0:
            return ExecutionOutcome(exit_code=exit_code, output=clean)
        try:
            data = json.loads(output)
        except json.JSONDecodeError as error:
            raise AdapterError("adapter.malformed_output", "Claude Code output is not valid JSON") from error
        if not isinstance(data, dict) or "result" not in data:
            raise AdapterError("adapter.malformed_output", "Claude Code output has no result field")
        failed = bool(data.get("is_error"))
        return ExecutionOutcome(
            exit_code=1 if failed else 0,
            output=sanitize(str(data["result"])),
            structured={"is_error": failed, "subtype": str(data.get("subtype", ""))},
        )
