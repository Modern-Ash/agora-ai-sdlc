from pathlib import Path
from types import SimpleNamespace

import pytest
from agora.model import AddArtifactInput, AddEvidenceInput, WorkActorInput
from agora.workspace import AgoraWorkspace
from support.lifecycle import Lifecycle

from agora_ai_sdlc.executor_recovery import ExecutorRecoveryChoice
from agora_ai_sdlc.guided_session import run_interactive
from agora_ai_sdlc.workflow_advisor import WorkflowAdvice
from agora_ai_sdlc.workflow_advisor import advise_workflow as real_advise_workflow


@pytest.fixture
def golden_life(tmp_path, monkeypatch):
    return Lifecycle(
        tmp_path / "project",
        tmp_path / "home",
        monkeypatch,
        method_version="0.2.0",
    )


def _artifact(root: Path, workspace: AgoraWorkspace, actor: str, kind: str) -> None:
    path = root / f"{kind}.md"
    path.write_text(f"# {kind}\n", encoding="utf-8")
    workspace.add_artifact(
        AddArtifactInput(
            swarm_id="delivery",
            work_id="feature",
            actor_id=actor,
            kind=kind,
            uri=f"repo://{kind}.md",
        )
    )


def _evidence(workspace: AgoraWorkspace, actor: str, kind: str) -> None:
    workspace.add_evidence(
        AddEvidenceInput(
            swarm_id="delivery",
            work_id="feature",
            actor_id=actor,
            type=kind,
            result="success",
            artifact_refs=[],
        )
    )


def _materialize_phase(root: Path, state: str) -> None:
    workspace = AgoraWorkspace(cwd=root)
    if state == "inception":
        workspace.satisfy_criterion(
            WorkActorInput(swarm_id="delivery", work_id="feature", actor_id="po"),
            "value",
            stage="elaborated",
        )
        for kind in (
            "intent",
            "plan",
            "requirements",
            "user-stories",
            "nfr",
            "risk-register",
            "measurement-criteria",
            "unit-of-work",
            "bolt-plan",
        ):
            _artifact(root, workspace, "po", kind)
        workspace.clarify_work(
            WorkActorInput(swarm_id="delivery", work_id="feature", actor_id="po"),
            runner="/bin/true",
        )
        return

    if state == "construction":
        actor = WorkActorInput(swarm_id="delivery", work_id="feature", actor_id="dev")
        for stage in ("designed", "built", "verified"):
            workspace.satisfy_criterion(actor, "value", stage=stage)
        for kind in (
            "domain-model",
            "logical-design",
            "implementation-plan",
            "test-strategy",
            "deployment-unit",
        ):
            _artifact(root, workspace, "dev", kind)
        _evidence(workspace, "dev", "test-suite")
        return

    if state == "operations":
        for kind in ("operational-readiness", "rollback-procedure"):
            _artifact(root, workspace, "dev", kind)
        _evidence(workspace, "dev", "deployment")
        _evidence(workspace, "dev", "security-scan")
        return

    raise AssertionError(f"unexpected generative phase {state}")


def test_single_aisdlc_flow_reaches_completed_without_side_commands_or_loops(monkeypatch, golden_life):
    """Product invariant: one guided aisdlc session must carry the normal delivery flow end to end."""

    root = golden_life.root
    outputs: list[str] = []
    prepare_states: list[str] = []
    actions: list[str] = []
    decisions: list[dict] = []
    prompts: list[str] = []
    runtime = ExecutorRecoveryChoice(
        agent="opencode",
        model="opencode/test-free",
        label="OpenCode · test-free [free]",
    )

    def advice(root_path, decision):
        decisions.append(decision.snapshot())
        if len(decisions) > 20:
            raise AssertionError(f"golden path exceeded 20 governed decisions; latest={decision.snapshot()!r}")
        technical_gap = bool(decision.missing_artifacts or decision.missing_evidence or decision.clarification_issues)
        if technical_gap:
            actions.append("prepare")
            return WorkflowAdvice(
                action="prepare",
                summary="Prepare the current phase technical obligations.",
                needs_runtime=True,
                source="deterministic",
                recommended_runtime=runtime,
            )
        result = real_advise_workflow(root_path, decision)
        actions.append(result.action)
        return result

    def execute(root_path, decision, **kwargs):
        prepare_states.append(decision.state)
        _materialize_phase(root_path, decision.state)
        return SimpleNamespace(
            runtime="OpenCode",
            result_path=str(root_path / f"{decision.state}-RESULT.md"),
        )

    monkeypatch.setattr("agora_ai_sdlc.guided_session.advise_workflow", advice)
    monkeypatch.setattr("agora_ai_sdlc.guided_session.execute_guided_preparation", execute)

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        if len(prompts) > 40:
            raise AssertionError(
                "golden path exceeded 40 user prompts; "
                f"latest_prompt={prompt!r}; "
                f"recent_actions={actions[-12:]!r}; "
                f"recent_decisions={decisions[-4:]!r}; "
                f"recent_output={outputs[-20:]!r}"
            )
        if "Respuesta" in prompt:
            return "No hay ambigüedad material; usar el criterio y alcance definidos en el Work."
        return ""

    result = run_interactive(
        root,
        swarm="delivery",
        work="feature",
        input_fn=answer,
        output_fn=outputs.append,
        lang="es",
    )

    final_work = golden_life.ws.show_work("delivery", "feature")

    assert result.reason == "completed"
    assert final_work.state == "completed"
    assert prepare_states == ["inception", "construction", "operations"]
    assert actions.count("prepare") == 3
    assert "mark-deployed" in actions
    assert "accept-criteria" in actions
    assert "review" not in actions
    assert not any("no reporta progreso gobernado" in line for line in outputs)
    assert any("Work completado; no quedan acciones gobernadas pendientes." in line for line in outputs)


def test_same_flow_uses_gate_obligation_actor_not_first_core_task(monkeypatch, golden_life):
    root = golden_life.root
    workspace = golden_life.ws

    workspace.satisfy_criterion(golden_life.wa("po"), "value", stage="elaborated")
    for kind in (
        "intent",
        "plan",
        "requirements",
        "user-stories",
        "nfr",
        "risk-register",
        "measurement-criteria",
        "unit-of-work",
        "bolt-plan",
    ):
        _artifact(root, workspace, "po", kind)
    golden_life.clarify()

    from agora_ai_sdlc.guided import inspect_next

    first = inspect_next(root, swarm="delivery", work="feature")
    assert first is not None
    assert first.missing_approvals
    assert first.role == first.missing_approvals[0]
    assert first.actor == workspace.show_swarm("delivery").assignments[first.role]
