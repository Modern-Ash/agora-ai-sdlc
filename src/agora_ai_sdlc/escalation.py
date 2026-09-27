"""Bounded diagnostic escalation and advisor hand-back.

A paid advisor never becomes the Work executor here. It receives a read-only,
bounded diagnostic envelope, returns advice, and the original cheap executor
may consume that advice in a subsequent governed execution attempt.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.execution_bundle import build_execution_bundle
from agora_ai_sdlc.execution_economics import EconomicsEvent, core_budgets, core_usage_snapshot, record_event
from agora_ai_sdlc.execution_envelope import ExecutionEnvelope
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.runtime_adapter import AdapterError, sanitize
from agora_ai_sdlc.runtime_domain import RuntimeBinding
from agora_ai_sdlc.runtime_pool import RuntimePoolError, select_from_runtime_pool
from agora_ai_sdlc.verification import persisted_verification_diagnostic

SCHEMA = "agora-ai-sdlc/escalation-package/v1"


class EscalationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class EscalationPackage:
    swarm: str
    work: str
    stage: str | None
    objective: str
    acceptance_criteria: tuple[str, ...]
    failed_agent: str
    failed_model: str | None
    failed_tier: str | None
    attempts: int
    error: str
    verification_diagnostic: str | None
    changed_paths: tuple[str, ...]
    dirty_paths: tuple[str, ...]
    verification_commands: tuple[str, ...]
    risks: tuple[str, ...]
    result_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body = {"schema": SCHEMA, **asdict(self)}
        payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return {**body, "digest": "sha256:" + hashlib.sha256(payload.encode()).hexdigest()}


@dataclass(frozen=True)
class AdvisorResult:
    binding: RuntimeBinding
    tier: str
    advice: str
    package_path: str
    advice_path: str


def build_escalation_package(
    root: Path,
    decision: Any,
    *,
    failed_agent: str,
    failed_model: str | None,
    failed_tier: str | None,
    attempts: int,
    error: BaseException | str,
    result_path: str | None = None,
) -> EscalationPackage:
    bundle = build_execution_bundle(
        root,
        swarm=decision.swarm,
        work=decision.work,
        persist=False,
    )
    diagnostic = persisted_verification_diagnostic(root, decision.work)
    return EscalationPackage(
        swarm=decision.swarm,
        work=decision.work,
        stage=bundle.stage,
        objective=bundle.objective or "",
        acceptance_criteria=tuple(bundle.acceptance_criteria),
        failed_agent=failed_agent,
        failed_model=failed_model,
        failed_tier=failed_tier,
        attempts=attempts,
        error=sanitize(str(error))[:1600],
        verification_diagnostic=diagnostic,
        changed_paths=tuple(bundle.changed_paths),
        dirty_paths=tuple(bundle.dirty_paths),
        verification_commands=tuple(bundle.verification_commands),
        risks=tuple(bundle.risks),
        result_path=result_path,
    )


def persist_package(root: Path, package: EscalationPackage) -> str:
    target = root / ".agora" / "ai-sdlc" / "escalations" / package.work / f"attempt-{package.attempts}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(package.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(target)


def _advisory_envelope(
    package: EscalationPackage,
    binding: RuntimeBinding,
    package_path: str,
) -> ExecutionEnvelope:
    requirements = requirements_for_activity("exploration.read_only", tier="standard")
    context = {
        "purpose": "diagnostic-advisor",
        "package": package_path,
        "instruction": (
            "Diagnose the bounded failure package. Do not modify files, run destructive commands, "
            "approve anything, or execute the Work transition. Return a concise repair plan for the "
            "original cheap executor."
        ),
    }
    return ExecutionEnvelope(
        package.swarm,
        package.work,
        "diagnostic-only",
        "project:diagnostic-advisor",
        "advisor",
        False,
        requirements.to_dict(),
        binding,
        "diagnostic.advise",
        (("work", package.work),),
        None,
        context,
    )


def _run(root: Path, argv: tuple[str, ...], stdin: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(argv),
            input=stdin,
            cwd=root,
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


def run_escalation_advisor(
    root: Path,
    package: EscalationPackage,
    *,
    availability=None,
    workspace=None,
) -> AdvisorResult:
    """Use the cheapest configured paid advisor and return read-only repair advice."""

    requirements = requirements_for_activity("exploration.read_only", tier="standard")
    try:
        selection = select_from_runtime_pool(
            root,
            requirements,
            availability=availability,
            budgets=core_budgets(workspace, package.swarm, package.work) if workspace is not None else (),
            work_id=package.work,
            minimum_tier="paid-efficient",
            maximum_tier="paid-standard",
            allowed_agents=("codex", "claude"),
        )
    except RuntimePoolError as error:
        raise EscalationError(error.code, str(error).split(": ", 1)[-1]) from error
    if selection is None:
        raise EscalationError("escalation.routing_unconfigured", "cheap-first routing is not configured")

    package_path = persist_package(root, package)
    envelope = _advisory_envelope(package, selection.binding, package_path)
    adapter = default_registry(root).get(selection.binding.agent)
    try:
        prepared = adapter.prepare_execution(envelope.to_dict())
        record_event(
            root,
            EconomicsEvent(
                "attempt",
                package.work,
                selection.tier,
                selection.binding.agent.id,
                selection.binding.model.model if selection.binding.model else None,
                purpose="diagnostic-advisor",
                reason="repeated-failure",
                core_usage=core_usage_snapshot(workspace, package.swarm, package.work) if workspace else None,
            ),
        )
        outcome = adapter.launch(prepared, lambda argv, stdin: _run(root, argv, stdin))
    except (AdapterError, OSError, RuntimeError, ValueError) as error:
        record_event(
            root,
            EconomicsEvent(
                "failure",
                package.work,
                selection.tier,
                selection.binding.agent.id,
                selection.binding.model.model if selection.binding.model else None,
                purpose="diagnostic-advisor",
                reason=error.__class__.__name__,
            ),
        )
        raise EscalationError("escalation.advisor_failed", str(error)) from error

    if outcome.exit_code != 0 or not outcome.output.strip():
        record_event(
            root,
            EconomicsEvent(
                "failure",
                package.work,
                selection.tier,
                selection.binding.agent.id,
                selection.binding.model.model if selection.binding.model else None,
                purpose="diagnostic-advisor",
                reason=f"advisor-exit-{outcome.exit_code}",
                exit_code=int(outcome.exit_code),
            ),
        )
        raise EscalationError("escalation.advisor_failed", f"advisor exited with {outcome.exit_code}")

    advice = sanitize(outcome.output).strip()
    advice_path = root / ".agora" / "ai-sdlc" / "escalations" / package.work / f"attempt-{package.attempts}-ADVICE.md"
    advice_path.write_text(advice + "\n", encoding="utf-8")
    record_event(
        root,
        EconomicsEvent(
            "success",
            package.work,
            selection.tier,
            selection.binding.agent.id,
            selection.binding.model.model if selection.binding.model else None,
            purpose="diagnostic-advisor",
            reason="repair-advice-produced",
            core_usage=core_usage_snapshot(workspace, package.swarm, package.work) if workspace else None,
        ),
    )
    record_event(
        root,
        EconomicsEvent(
            "escalation",
            package.work,
            selection.tier,
            selection.binding.agent.id,
            selection.binding.model.model if selection.binding.model else None,
            purpose="diagnostic-advisor",
            reason="repeated-failure",
        ),
    )
    return AdvisorResult(selection.binding, selection.tier, advice, package_path, str(advice_path))
