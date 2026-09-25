from pathlib import Path
from types import SimpleNamespace

from agora_ai_sdlc.executor_recovery import ExecutorRecoveryChoice
from agora_ai_sdlc.guided import GuidedDecision
from agora_ai_sdlc.workflow_advisor import advise_workflow


def context_selection():
    return SimpleNamespace(
        candidate_paths=("src/a.py", "src/b.py"),
        selected_paths=("src/a.py",),
        candidate_tokens=1200,
        selected_tokens=500,
        saved_tokens=700,
        reduction_ratio=700 / 1200,
        escalated_paths=(),
    )


def decision(**changes):
    values = {
        "swarm": "delivery",
        "work": "issue-26",
        "title": "Deliver issue",
        "method": "ai-sdlc",
        "actor": "project:developer",
        "role": "developer",
        "state": "construction",
        "target": "operations",
        "gate": "construction-complete",
        "blockers": ("blocked",),
        "messages": ("Prepare missing work.",),
        "missing_artifacts": ("implementation-plan",),
        "missing_evidence": (),
        "missing_approvals": (),
        "unsatisfied_criteria": (),
        "git_issues": (),
        "clarification_issues": (),
        "ready_for_human_approval": False,
        "ready_to_transition": False,
    }
    values.update(changes)
    return GuidedDecision(**values)


def test_human_approval_never_uses_laya(monkeypatch):
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.build_execution_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not call Laya path")),
    )
    advice = advise_workflow(
        Path("."),
        decision(
            ready_for_human_approval=True,
            missing_approvals=("product-owner",),
        ),
    )
    assert advice.action == "approve"
    assert advice.source == "deterministic"
    assert not advice.needs_runtime


def test_low_cost_work_preselects_local_free_runtime(monkeypatch):
    answer = SimpleNamespace(value="local", confidence=0.97)
    evaluation = SimpleNamespace(
        result=SimpleNamespace(answers={"reasoning_tier": answer}),
        escalated=(),
    )

    monkeypatch.setattr("agora_ai_sdlc.workflow_advisor.build_execution_bundle", lambda *args, **kwargs: object())
    monkeypatch.setattr("agora_ai_sdlc.workflow_advisor.advise_execution", lambda *args, **kwargs: evaluation)
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor._free_runtime",
        lambda root: ExecutorRecoveryChoice("opencode", "ollama/qwen3:8b", "Ollama · qwen3:8b [local]"),
    )

    advice = advise_workflow(Path("."), decision())
    assert advice.action == "prepare"
    assert advice.source == "laya"
    assert advice.reasoning_tier == "local"
    assert advice.confidence == 0.97
    assert advice.recommended_runtime is not None
    assert "[local]" in advice.recommended_runtime.label
    assert advice.context_candidates == 0
    assert advice.context_selected == 0
    assert advice.context_tokens_saved == 0


def test_uncertain_laya_never_suppresses_normal_escalation(monkeypatch):
    answer = SimpleNamespace(value="local", confidence=0.51)
    evaluation = SimpleNamespace(
        result=SimpleNamespace(answers={"reasoning_tier": answer}),
        escalated=("reasoning_tier",),
    )

    monkeypatch.setattr("agora_ai_sdlc.workflow_advisor.build_execution_bundle", lambda *args, **kwargs: object())
    monkeypatch.setattr("agora_ai_sdlc.workflow_advisor.advise_execution", lambda *args, **kwargs: evaluation)
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor._free_runtime",
        lambda root: (_ for _ in ()).throw(AssertionError("uncertain result must not auto-select")),
    )

    advice = advise_workflow(Path("."), decision())
    assert advice.action == "prepare"
    assert advice.escalation_required
    assert advice.recommended_runtime is None


def test_preconfirmation_advice_does_not_select_per_file_context(monkeypatch):
    answer = SimpleNamespace(value="standard", confidence=0.96)
    evaluation = SimpleNamespace(
        result=SimpleNamespace(answers={"reasoning_tier": answer}),
        escalated=(),
    )

    monkeypatch.setattr("agora_ai_sdlc.workflow_advisor.build_execution_bundle", lambda *args, **kwargs: object())
    monkeypatch.setattr("agora_ai_sdlc.workflow_advisor.advise_execution", lambda *args, **kwargs: evaluation)
    monkeypatch.setattr("agora_ai_sdlc.workflow_advisor._free_runtime", lambda root: None)

    advice = advise_workflow(Path("."), decision())

    assert advice.action == "prepare"
    assert advice.context_candidates == 0
    assert advice.context_selected == 0
    assert advice.context_tokens_before == 0
    assert advice.context_tokens_after == 0


def test_final_criterion_acceptance_is_human_and_never_uses_laya(monkeypatch):
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.build_execution_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("final acceptance must not call Laya")),
    )

    advice = advise_workflow(
        Path("."),
        decision(
            actor="project:product-owner",
            role="product-owner",
            state="operations",
            target="completed",
            gate="completion",
            blockers=("unsatisfied=[source-issue]",),
            messages=("Complete criteria.",),
            missing_artifacts=(),
            missing_evidence=(),
            missing_approvals=(),
            unsatisfied_criteria=("source-issue",),
            criterion_statuses=(("source-issue", ("elaborated", "designed", "built", "verified", "deployed")),),
        ),
    )

    assert advice.action == "accept-criteria"
    assert advice.source == "deterministic"
    assert advice.needs_runtime is False


def test_verified_final_criterion_uses_assigned_ai_developer_without_laya(monkeypatch):
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.pull_request_delivery_enabled",
        lambda root: False,
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.build_execution_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("deployed stage must not call Laya")),
    )

    advice = advise_workflow(
        Path("."),
        decision(
            actor="project:product-owner",
            role="product-owner",
            state="operations",
            target="completed",
            gate="completion",
            blockers=("unsatisfied=[source-issue]",),
            messages=("Complete criteria.",),
            missing_artifacts=(),
            missing_evidence=(),
            missing_approvals=(),
            unsatisfied_criteria=("source-issue",),
            criterion_statuses=(("source-issue", ("elaborated", "designed", "built", "verified")),),
            developer_actor="project:ai-developer",
            developer_actor_kind="ai-agent",
        ),
    )

    assert advice.action == "mark-deployed"
    assert advice.source == "deterministic"
    assert advice.needs_runtime is False


def test_verified_final_criterion_with_human_developer_stays_at_review_boundary(monkeypatch):
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.build_execution_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("human developer boundary must not call Laya")),
    )

    advice = advise_workflow(
        Path("."),
        decision(
            actor="project:product-owner",
            role="product-owner",
            state="operations",
            target="completed",
            gate="completion",
            blockers=("unsatisfied=[source-issue]",),
            messages=("Complete criteria.",),
            missing_artifacts=(),
            missing_evidence=(),
            missing_approvals=(),
            unsatisfied_criteria=("source-issue",),
            criterion_statuses=(("source-issue", ("elaborated", "designed", "built", "verified")),),
            developer_actor="project:developer",
            developer_actor_kind="human",
        ),
    )

    assert advice.action == "review"
    assert advice.needs_runtime is False


def test_construction_progresses_evidenced_criterion_stage_without_llm(monkeypatch):
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.build_execution_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("criterion progression must not call Laya")),
    )

    advice = advise_workflow(
        Path("."),
        decision(
            state="construction",
            target="operations",
            gate="construction-verified",
            blockers=("unsatisfied=[source-issue]",),
            messages=("Complete criteria.",),
            missing_artifacts=(),
            missing_evidence=(),
            missing_approvals=(),
            unsatisfied_criteria=("source-issue",),
            criterion_statuses=(("source-issue", ("elaborated", "designed")),),
            developer_actor="project:ai-developer",
            developer_actor_kind="ai-agent",
            next_criterion_stage="built",
        ),
    )

    assert advice.action == "advance-criterion"
    assert advice.source == "deterministic"
    assert advice.needs_runtime is False


def test_pull_request_delivery_replaces_fake_deployment_prepare(monkeypatch):
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.pull_request_delivery_enabled",
        lambda root: True,
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.build_execution_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("PR delivery must not call Laya")),
    )

    advice = advise_workflow(
        Path("."),
        decision(
            actor="project:product-owner",
            role="product-owner",
            state="operations",
            target="completed",
            gate="completion",
            blockers=("unsatisfied=[source-issue]", "missing-evidence-types=[deployment]"),
            messages=("Deploy or publish.",),
            missing_artifacts=(),
            missing_evidence=("deployment",),
            missing_approvals=(),
            unsatisfied_criteria=("source-issue",),
            criterion_statuses=(("source-issue", ("elaborated", "designed", "built", "verified")),),
            developer_actor="project:ai-codex",
            developer_actor_kind="ai-agent",
        ),
    )

    assert advice.action == "submit-pr"
    assert advice.needs_runtime is False
    assert advice.source == "deterministic"


def test_built_construction_with_missing_test_evidence_verifies_without_llm(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.persisted_verification_failed",
        lambda root, work: False,
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.build_execution_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("testing boundary must not call Laya")),
    )

    advice = advise_workflow(
        tmp_path,
        decision(
            state="construction",
            target="operations",
            gate="construction-verified",
            blockers=("unsatisfied=[source-issue]", "missing-evidence-types=[test-suite]"),
            messages=("Verify implementation.",),
            missing_artifacts=(),
            missing_evidence=("test-suite",),
            missing_approvals=(),
            unsatisfied_criteria=("source-issue",),
            criterion_statuses=(("source-issue", ("elaborated", "designed", "built")),),
            developer_actor="project:ai-developer",
            developer_actor_kind="ai-agent",
        ),
    )

    assert advice.action == "verify"
    assert advice.needs_runtime is False
    assert advice.source == "deterministic"


def test_failed_construction_verification_returns_to_agent_repair(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.persisted_verification_failed",
        lambda root, work: True,
    )
    monkeypatch.setattr(
        "agora_ai_sdlc.workflow_advisor.build_execution_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("failed verification repair is deterministic routing")),
    )

    advice = advise_workflow(
        tmp_path,
        decision(
            state="construction",
            target="operations",
            gate="construction-verified",
            blockers=("unsatisfied=[source-issue]", "missing-evidence-types=[test-suite]"),
            messages=("Repair tests.",),
            missing_artifacts=(),
            missing_evidence=("test-suite",),
            missing_approvals=(),
            unsatisfied_criteria=("source-issue",),
            criterion_statuses=(("source-issue", ("elaborated", "designed", "built")),),
            developer_actor="project:ai-developer",
            developer_actor_kind="ai-agent",
        ),
    )

    assert advice.action == "prepare"
    assert advice.needs_runtime is True
    assert advice.source == "deterministic"
