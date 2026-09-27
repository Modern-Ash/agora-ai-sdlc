"""Bounded diagnostic escalation and advisor hand-back.

A paid advisor never becomes the Work executor here. It receives a read-only,
bounded diagnostic envelope, returns advice, and the original cheap executor
may consume that advice in a subsequent governed execution attempt.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agora.model import AddUsageInput

from agora_ai_sdlc.execution_bundle import build_execution_bundle
from agora_ai_sdlc.execution_economics import (
    EconomicsEvent,
    core_budgets,
    core_usage_snapshot,
    record_event,
)
from agora_ai_sdlc.execution_requirements import requirements_for_activity
from agora_ai_sdlc.repair_advice import render_executor_handback
from agora_ai_sdlc.runtime_adapter import sanitize
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


def _record_planner_usage(
    root: Path,
    package: EscalationPackage,
    *,
    workspace: Any | None,
    actor_id: str | None,
    tier: str,
    binding: RuntimeBinding,
    usage: dict[str, int],
    advice_path: str,
) -> bool:
    model = binding.model.model if binding.model is not None else None
    if not usage or workspace is None or not actor_id:
        record_event(
            root,
            EconomicsEvent(
                "planner-usage-unaccounted",
                package.work,
                tier,
                binding.agent.id,
                model,
                purpose="diagnostic-advisor",
                reason="provider-telemetry-or-core-actor-unavailable",
            ),
        )
        return False

    digest = str(package.to_dict()["digest"]).removeprefix("sha256:")[:12]
    usage_id = f"planner-{package.attempts}-{digest}"
    try:
        existing = getattr(workspace, "list_usage", lambda *_: [])(package.swarm, package.work)
        if not any(getattr(item, "id", None) == usage_id for item in existing):
            usage_kwargs = {
                "id": usage_id,
                "swarm_id": package.swarm,
                "work_id": package.work,
                "actor_id": actor_id,
                "amounts": dict(usage),
                "evidence_refs": [
                    "repo://" + str(Path(advice_path).resolve().relative_to(root.resolve())),
                ],
            }
            usage_fields = getattr(AddUsageInput, "__dataclass_fields__", {})
            if "measurement" in usage_fields:
                usage_kwargs["measurement"] = "provider-reported"
            workspace.add_usage(AddUsageInput(**usage_kwargs))
    except (OSError, PermissionError, RuntimeError, ValueError) as error:
        record_event(
            root,
            EconomicsEvent(
                "planner-usage-unaccounted",
                package.work,
                tier,
                binding.agent.id,
                model,
                purpose="diagnostic-advisor",
                reason=str(error),
            ),
        )
        return False

    record_event(
        root,
        EconomicsEvent(
            "planner-usage-recorded",
            package.work,
            tier,
            binding.agent.id,
            model,
            purpose="diagnostic-advisor",
            reason=(
                "provider-reported"
                if "measurement" in getattr(AddUsageInput, "__dataclass_fields__", {})
                else "provider-reported-core-legacy"
            ),
            core_usage=core_usage_snapshot(workspace, package.swarm, package.work),
        ),
    )
    return True


def run_escalation_advisor(
    root: Path,
    package: EscalationPackage,
    *,
    availability=None,
    workspace=None,
    actor_id: str | None = None,
) -> AdvisorResult:
    """Use the cheapest permitted paid planner, read-only, then hand advice back."""

    from agora_ai_sdlc.advisory_planner import AdvisoryPlannerError, run_advisory_planner

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
            purpose="planner",
        )
    except RuntimePoolError as error:
        raise EscalationError(error.code, str(error).split(": ", 1)[-1]) from error
    if selection is None:
        raise EscalationError("escalation.routing_unconfigured", "cheap-first routing is not configured")

    package_path = persist_package(root, package)
    model = selection.binding.model.model if selection.binding.model is not None else None
    record_event(
        root,
        EconomicsEvent(
            "attempt",
            package.work,
            selection.tier,
            selection.binding.agent.id,
            model,
            purpose="diagnostic-advisor",
            reason="repeated-failure",
            core_usage=core_usage_snapshot(workspace, package.swarm, package.work) if workspace else None,
        ),
    )

    try:
        outcome = run_advisory_planner(
            root,
            package=package,
            binding=selection.binding,
            tier=selection.tier,
        )
    except (AdvisoryPlannerError, OSError, RuntimeError, ValueError) as error:
        record_event(
            root,
            EconomicsEvent(
                "failure",
                package.work,
                selection.tier,
                selection.binding.agent.id,
                model,
                purpose="diagnostic-advisor",
                reason=error.__class__.__name__,
            ),
        )
        raise EscalationError("escalation.advisor_failed", str(error)) from error

    _record_planner_usage(
        root,
        package,
        workspace=workspace,
        actor_id=actor_id,
        tier=selection.tier,
        binding=selection.binding,
        usage=outcome.usage,
        advice_path=outcome.path,
    )
    advice = render_executor_handback(outcome.advice)

    record_event(
        root,
        EconomicsEvent(
            "success",
            package.work,
            selection.tier,
            selection.binding.agent.id,
            model,
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
            model,
            purpose="diagnostic-advisor",
            reason="repeated-failure",
        ),
    )
    return AdvisorResult(selection.binding, selection.tier, advice, package_path, outcome.path)
