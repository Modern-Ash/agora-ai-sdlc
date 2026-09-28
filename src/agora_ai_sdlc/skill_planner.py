"""Bounded paid skill planning with cheap-executor handoff.

The planner interprets the installed AI-SDLC skill and a deterministic execution
bundle. It is read-only, non-authoritative and intentionally separate from the
runtime that performs repository writes. Identical planning inputs are reused
so retries do not repeatedly consume a paid model.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agora_ai_sdlc.adapters import default_registry
from agora_ai_sdlc.execution_bundle import ExecutionBundle
from agora_ai_sdlc.execution_economics import EconomicsEvent, core_budgets, core_usage_snapshot, record_event
from agora_ai_sdlc.execution_envelope import ExecutionEnvelope
from agora_ai_sdlc.execution_policy import execution_policy_for
from agora_ai_sdlc.execution_requirements import requirements_for, requirements_for_activity
from agora_ai_sdlc.laya_provider import LayaDecisionProvider
from agora_ai_sdlc.runtime_adapter import AdapterError, sanitize
from agora_ai_sdlc.runtime_domain import AgentRuntimeRef, ModelRuntimeRef, RuntimeBinding
from agora_ai_sdlc.runtime_pool import RuntimePoolError, select_from_runtime_pool

SCHEMA = "agora-ai-sdlc/skill-plan/v1"
_MAX_SKILL_CHARS = 12000
_MAX_PHASE_CHARS = 10000
_MAX_PLAN_CHARS = 12000


@dataclass(frozen=True)
class SkillPlan:
    binding: RuntimeBinding
    tier: str
    text: str
    path: str
    input_digest: str
    reused: bool


def _read(path: Path, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()[:limit]
    except OSError:
        return ""


def _skill_context(root: Path, stage: str | None) -> tuple[str, str]:
    local = root / ".agora" / "skills" / "agora-ai-sdlc-guided"
    skill = _read(local / "SKILL.md", _MAX_SKILL_CHARS)
    phase = _read(local / "references" / f"{stage}.md", _MAX_PHASE_CHARS) if stage else ""
    return skill, phase


def _input_body(bundle: ExecutionBundle, skill: str, phase: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "work": {"swarm": bundle.swarm, "id": bundle.work, "stage": bundle.stage},
        "objective": bundle.objective,
        "acceptance_criteria": list(bundle.acceptance_criteria),
        "changed_paths": list(bundle.changed_paths),
        "dirty_paths": list(bundle.dirty_paths),
        "related_paths": list(bundle.related_paths),
        "verification_commands": list(bundle.verification_commands),
        "risks": list(bundle.risks),
        "skill": skill,
        "phase_guidance": phase,
    }


def _digest(body: dict[str, Any]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _paths(root: Path, work: str, stage: str | None) -> tuple[Path, Path]:
    directory = root / ".agora" / "ai-sdlc" / "planning" / work
    name = stage or "step"
    return directory / f"{name}.json", directory / f"{name}-PLAN.md"


def _cached(root: Path, bundle: ExecutionBundle, digest: str) -> SkillPlan | None:
    meta_path, plan_path = _paths(root, str(bundle.work), bundle.stage)
    if not meta_path.is_file() or not plan_path.is_file():
        return None
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if metadata.get("schema") != SCHEMA or metadata.get("input_digest") != digest:
        return None
    runtime = metadata.get("runtime") or {}
    agent = runtime.get("agent") or {}
    model = runtime.get("model")
    if not isinstance(agent, dict):
        return None
    agent_id = str(agent.get("id") or "")
    integration = str(agent.get("integration") or "")
    if not agent_id or not integration:
        return None
    model_ref = None
    if isinstance(model, dict):
        provider = str(model.get("provider") or "")
        model_name = str(model.get("model") or "")
        if provider and model_name:
            model_ref = ModelRuntimeRef(str(model.get("id") or provider), provider, model_name)
    binding = RuntimeBinding(AgentRuntimeRef(agent_id, integration), model_ref)
    try:
        text = plan_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    return SkillPlan(
        binding=binding,
        tier=str(metadata.get("tier") or "paid-efficient"),
        text=text,
        path=str(plan_path),
        input_digest=digest,
        reused=True,
    )


def _persist(
    root: Path,
    bundle: ExecutionBundle,
    *,
    selection,
    digest: str,
    plan: str,
) -> SkillPlan:
    meta_path, plan_path = _paths(root, str(bundle.work), bundle.stage)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan.rstrip() + "\n", encoding="utf-8")
    metadata = {
        "schema": SCHEMA,
        "input_digest": digest,
        "tier": selection.tier,
        "runtime": selection.binding.to_dict(),
        "plan": str(plan_path.relative_to(root)),
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SkillPlan(
        binding=selection.binding,
        tier=selection.tier,
        text=plan,
        path=str(plan_path),
        input_digest=digest,
        reused=False,
    )


def _envelope(bundle: ExecutionBundle, binding: RuntimeBinding, body: dict[str, Any], digest: str) -> ExecutionEnvelope:
    requirements = requirements_for_activity("exploration.read_only", tier="standard")
    return ExecutionEnvelope(
        str(bundle.swarm or "delivery"),
        str(bundle.work or "unknown"),
        digest,
        "project:skill-planner",
        "planner",
        False,
        requirements.to_dict(),
        binding,
        "planning.advise",
        (("work", str(bundle.work or "unknown")),),
        None,
        {
            "purpose": "skill-planner",
            "instruction": (
                "Interpret the bounded Agora AI-SDLC skill and produce a concise implementation plan for another executor. "
                "Do not modify files, run destructive commands, approve, transition lifecycle state, or claim completion. "
                "Prefer exact steps, files, checks and constraints. The plan is advisory and must fit the supplied scope."
            ),
            "planning_input": body,
        },
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
        output += ("\n" if output else "") + result.stderr
    return result.returncode, output


def maybe_plan_skill(
    root: Path,
    bundle: ExecutionBundle,
    *,
    availability=None,
    workspace=None,
) -> SkillPlan | None:
    """Run the cheapest permitted paid planner when policy asks for one.

    Absence/failure of the optional planner fails open to the normal executor.
    """

    try:
        requirements = requirements_for(bundle, provider=LayaDecisionProvider())
        policy = execution_policy_for(requirements)
    except (AttributeError, OSError, RuntimeError, ValueError):
        # Skill planning is an optional advisory optimization. Legacy/minimal
        # execution-bundle seams used by supported executors may not expose the
        # full canonical bundle contract, so planning must fail open rather
        # than breaking the underlying governed execution path.
        return None
    if policy.planner_tier is None:
        # none/template planning is already represented by the deterministic
        # execution bundle + phase guidance; no generative planner is needed.
        return None

    skill, phase = _skill_context(root, bundle.stage)
    body = _input_body(bundle, skill, phase)
    digest = _digest(body)
    cached = _cached(root, bundle, digest)
    if cached is not None:
        return cached

    planner_reasoning = "local" if policy.planner_mode == "local" else (
        "frontier" if policy.planner_mode == "frontier" else "standard"
    )
    planner_requirements = requirements_for_activity("exploration.read_only", tier=planner_reasoning)
    minimum_tier = "local" if policy.planner_mode == "local" else (
        "frontier" if policy.planner_mode == "frontier" else "paid-efficient"
    )
    allowed_agents = None if policy.planner_mode == "local" else ("codex", "claude")
    try:
        selection = select_from_runtime_pool(
            root,
            planner_requirements,
            availability=availability,
            budgets=core_budgets(workspace, str(bundle.swarm), str(bundle.work)) if workspace is not None else (),
            work_id=str(bundle.work or "unknown"),
            minimum_tier=minimum_tier,
            maximum_tier=policy.planner_tier,
            allowed_agents=allowed_agents,
            purpose="planner",
        )
    except RuntimePoolError:
        return None
    if selection is None:
        return None

    envelope = _envelope(bundle, selection.binding, body, digest)
    adapter = default_registry(root).get(selection.binding.agent)
    model = selection.binding.model.model if selection.binding.model else None
    try:
        prepared = adapter.prepare_execution(envelope.to_dict())
        record_event(
            root,
            EconomicsEvent(
                "attempt",
                str(bundle.work or "unknown"),
                selection.tier,
                selection.binding.agent.id,
                model,
                purpose="skill-planner",
                reason="policy-planner",
                core_usage=(
                    core_usage_snapshot(workspace, str(bundle.swarm), str(bundle.work))
                    if workspace is not None
                    else None
                ),
            ),
        )
        outcome = adapter.launch(prepared, lambda argv, stdin: _run(root, argv, stdin))
    except (AdapterError, OSError, RuntimeError, ValueError):
        record_event(
            root,
            EconomicsEvent(
                "failure",
                str(bundle.work or "unknown"),
                selection.tier,
                selection.binding.agent.id,
                model,
                purpose="skill-planner",
                reason="planner-launch-failed",
            ),
        )
        return None

    if outcome.exit_code != 0 or not outcome.output.strip():
        record_event(
            root,
            EconomicsEvent(
                "failure",
                str(bundle.work or "unknown"),
                selection.tier,
                selection.binding.agent.id,
                model,
                purpose="skill-planner",
                reason=f"planner-exit-{outcome.exit_code}",
                exit_code=int(outcome.exit_code),
            ),
        )
        return None

    plan = sanitize(outcome.output).strip()[:_MAX_PLAN_CHARS]
    record_event(
        root,
        EconomicsEvent(
            "success",
            str(bundle.work or "unknown"),
            selection.tier,
            selection.binding.agent.id,
            model,
            purpose="skill-planner",
            reason="plan-produced",
            core_usage=(
                core_usage_snapshot(workspace, str(bundle.swarm), str(bundle.work)) if workspace is not None else None
            ),
        ),
    )
    return _persist(root, bundle, selection=selection, digest=digest, plan=plan)
