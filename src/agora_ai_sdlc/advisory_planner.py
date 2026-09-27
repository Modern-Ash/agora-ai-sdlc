"""Read-only advisory planner transport for bounded escalations.

Planner invocations are deliberately separate from governed execution. They may
inspect the repository and the persisted EscalationPackage, but they cannot
write files, record evidence, approve gates, or transition lifecycle state.
Their only durable output is RepairAdvice.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agora_ai_sdlc.escalation import EscalationPackage
from agora_ai_sdlc.repair_advice import RepairAdvice, build_repair_advice, persist_repair_advice
from agora_ai_sdlc.runtime_adapter import sanitize
from agora_ai_sdlc.runtime_domain import RuntimeBinding

_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\\[\\]-]{0,63}$")
_DEFAULT = {"", "default", "configured-default"}
_FENCE = chr(96) * 3
Runner = Callable[[tuple[str, ...], str, Path], tuple[int, str]]


class AdvisoryPlannerError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {sanitize(message)}")
        self.code = code


@dataclass(frozen=True)
class PlannerOutcome:
    advice: RepairAdvice
    path: str
    raw_output: str


def _subprocess_runner(argv: tuple[str, ...], stdin: str, root: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(argv),
            input=stdin,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 127, error.__class__.__name__
    output = result.stdout or ""
    if result.stderr:
        output += ("\\n" if output else "") + result.stderr
    return result.returncode, output


def _model(binding: RuntimeBinding) -> str | None:
    value = binding.model
    if value is None or value.model.casefold() in _DEFAULT:
        return None
    if not _SAFE_MODEL.match(value.model):
        raise AdvisoryPlannerError("planner.model_invalid", "planner model contains unsafe characters")
    return value.model


def _invocation(binding: RuntimeBinding, root: Path) -> tuple[tuple[str, ...], str]:
    agent = binding.agent.id
    if binding.model is not None:
        provider = binding.model.provider.casefold()
        if agent == "codex" and provider != "openai":
            raise AdvisoryPlannerError(
                "planner.model_unsupported",
                f"Codex planner cannot serve provider {binding.model.provider!r}",
            )
        if agent == "claude" and provider != "anthropic":
            raise AdvisoryPlannerError(
                "planner.model_unsupported",
                f"Claude planner cannot serve provider {binding.model.provider!r}",
            )
    model = _model(binding)
    model_flags = () if model is None else ("--model", model)

    if agent == "codex":
        executable = shutil.which("codex")
        if executable is None:
            raise AdvisoryPlannerError("planner.unavailable", "Codex executable is unavailable")
        return (
            (
                executable,
                "exec",
                "--ephemeral",
                "--color",
                "never",
                "--sandbox",
                "read-only",
                *model_flags,
                "-",
            ),
            "raw",
        )

    if agent == "claude":
        executable = shutil.which("claude")
        if executable is None:
            raise AdvisoryPlannerError("planner.unavailable", "Claude executable is unavailable")
        argv = [
            executable,
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--permission-mode",
            "acceptEdits",
            *model_flags,
            "--allowedTools",
            "Read",
            "Bash(git status:*)",
            "Bash(git diff:*)",
        ]
        return tuple(argv), "claude-json"

    raise AdvisoryPlannerError(
        "planner.unsupported_agent",
        f"read-only advisory planning is not implemented for agent {agent!r}",
    )


def _prompt(package: EscalationPackage) -> str:
    payload = package.to_dict()
    return (
        "You are an advisory planner in Agora AI-SDLC. You are READ-ONLY. "
        "Do not edit files, run mutation commands, record evidence, approve anything, "
        "or transition lifecycle state. Analyze only the bounded escalation package and, "
        "when useful, read the minimum repository context needed to diagnose it. "
        "Return ONLY JSON with this shape: "
        '{"summary":"short diagnosis","actions":["bounded repair action","..."]}. '
        "Actions are advice for a separate cheap executor; they are not authority.\\n\\n"
        + json.dumps(payload, sort_keys=True, indent=2)
    )


def _extract_json(text: str) -> dict:
    clean = text.strip()
    if clean.startswith(_FENCE):
        if clean.startswith(_FENCE + "json"):
            clean = clean[len(_FENCE) + 4 :].lstrip()
        else:
            clean = clean[len(_FENCE) :].lstrip()
        if clean.endswith(_FENCE):
            clean = clean[: -len(_FENCE)].rstrip()
    try:
        value = json.loads(clean)
    except json.JSONDecodeError:
        start, end = clean.find("{"), clean.rfind("}")
        if start < 0 or end <= start:
            raise AdvisoryPlannerError("planner.malformed_output", "planner returned no JSON object")
        try:
            value = json.loads(clean[start : end + 1])
        except json.JSONDecodeError as error:
            raise AdvisoryPlannerError("planner.malformed_output", "planner returned invalid JSON") from error
    if not isinstance(value, dict):
        raise AdvisoryPlannerError("planner.malformed_output", "planner output must be a JSON object")
    return value


def _payload(output: str, mode: str) -> dict:
    if mode == "claude-json":
        outer = _extract_json(output)
        result = outer.get("result")
        if not isinstance(result, str):
            raise AdvisoryPlannerError("planner.malformed_output", "Claude planner output has no result text")
        return _extract_json(result)
    return _extract_json(output)


def run_advisory_planner(
    root: Path,
    *,
    package: EscalationPackage,
    binding: RuntimeBinding,
    tier: str,
    runner: Runner = _subprocess_runner,
) -> PlannerOutcome:
    argv, mode = _invocation(binding, root)
    code, output = runner(argv, _prompt(package), root)
    if code != 0:
        raise AdvisoryPlannerError("planner.failed", f"planner exited with code {code}: {output}")
    data = _payload(output, mode)
    summary = data.get("summary")
    actions = data.get("actions")
    if (
        not isinstance(summary, str)
        or not isinstance(actions, list)
        or any(not isinstance(item, str) for item in actions)
    ):
        raise AdvisoryPlannerError("planner.malformed_output", "planner requires summary and string-list actions")
    advice = build_repair_advice(
        work=package.work,
        escalation_digest=package.digest,
        planner_tier=tier,
        planner_agent=binding.agent.id,
        summary=summary,
        actions=tuple(actions),
    )
    path = persist_repair_advice(root, advice)
    return PlannerOutcome(advice=advice, path=str(path), raw_output=sanitize(output)[:6000])
