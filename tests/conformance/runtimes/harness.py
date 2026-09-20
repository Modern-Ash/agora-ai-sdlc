"""Run adapter-shaped fake sessions through Agora Core and normalize their semantics."""

import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from agora.model import (
    AddActorInput,
    AddArtifactInput,
    AddEvidenceInput,
    AssignActorInput,
    CreateSwarmInput,
    CreateWorkInput,
    InitInput,
    SetActorRuntimeInput,
    StartSessionInput,
)
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.data_classification import (
    ClassifiedInput,
    RuntimeEligibility,
    evaluate_launch,
)
from agora_ai_sdlc.independent_review import ArtifactRevision, Review, evaluate_review
from agora_ai_sdlc.provenance import Value, parse
from agora_ai_sdlc.runtime_selection import Candidate, Route, RuntimeRef, select_runtime

HERE = Path(__file__).parent
FAKE_RUNNER = HERE / "fake_runner.py"


@dataclass(frozen=True)
class RuntimeSpec:
    integration: str
    provider: str
    model: str


def normalize_output(adapter: str, raw: str) -> dict:
    """Normalize fake adapter envelopes before any cross-runtime assertion."""
    if adapter == "codex":
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
        envelope = next(record for record in records if record.get("type") == "turn.completed")
        result, usage = envelope["result"], envelope["usage"]
        return {
            "outcome": result["outcome"],
            "phase": result["phase"],
            "artifact": result["artifact"],
            "tokens": {"input": usage["input_tokens"], "output": usage["output_tokens"]},
        }
    envelope = json.loads(raw)
    if adapter == "claude":
        return {
            "outcome": "failure" if envelope["is_error"] else "success",
            "phase": envelope["result"]["phase"],
            "artifact": envelope["result"]["artifact"],
            "tokens": {
                "input": envelope["usage"]["input_tokens"],
                "output": envelope["usage"]["output_tokens"],
            },
        }
    if adapter == "generic":
        return {
            "outcome": "success" if envelope["status"] == "ok" else "failure",
            "phase": envelope["payload"]["phase"],
            "artifact": envelope["payload"]["artifact"],
            "tokens": {
                "input": envelope["metrics"]["prompt_tokens"],
                "output": envelope["metrics"]["completion_tokens"],
            },
        }
    raise ValueError(f"unsupported adapter: {adapter}")


def _runner(adapter: str, phase: str, capture: Path) -> str:
    return shlex.join(
        [
            sys.executable,
            str(FAKE_RUNNER),
            "--adapter",
            adapter,
            "--phase",
            phase,
            "--capture",
            str(capture),
        ]
    )


def _actor(actor_id: str, kind: str, capabilities: list[str]) -> AddActorInput:
    return AddActorInput(
        id=actor_id,
        name=actor_id,
        kind=kind,
        capabilities=capabilities,
        scope="project",
    )


def _workspace(root: Path, reviewer_kind: str, same_actor: bool) -> AgoraWorkspace:
    workspace = AgoraWorkspace(cwd=root)
    workspace.initialize(
        InitInput(
            integration="generic",
            provider="conformance",
            model="fake",
            default_method="scrum",
        )
    )
    workspace.add_actor(_actor("owner", "human", ["backlog-management", "acceptance"]))
    if same_actor:
        workspace.add_actor(_actor("worker", "ai-agent", ["implementation", "facilitation", "governance"]))
        producer_id = reviewer_id = "worker"
    else:
        workspace.add_actor(_actor("producer", "ai-agent", ["implementation"]))
        workspace.add_actor(_actor("reviewer", reviewer_kind, ["facilitation", "governance"]))
        producer_id, reviewer_id = "producer", "reviewer"
    workspace.create_swarm(CreateSwarmInput(id="delivery", objective="Runtime conformance", create_branch=False))
    for role, actor in (
        ("product-owner", "owner"),
        ("developer", producer_id),
        ("scrum-master", reviewer_id),
    ):
        workspace.assign_actor(AssignActorInput(swarm_id="delivery", role_id=role, actor_id=actor))
    workspace.create_work(
        CreateWorkInput(
            swarm_id="delivery",
            id="increment",
            title="Conformance increment",
            actor_id="owner",
            acceptance_criteria=[("normalized", "Runtime outcomes normalize identically")],
        )
    )
    return workspace


def _session(
    workspace: AgoraWorkspace,
    root: Path,
    *,
    session_id: str,
    actor_id: str,
    runtime: RuntimeSpec,
    phase: str,
):
    workspace.set_actor_runtime(
        SetActorRuntimeInput(
            actor_id=actor_id,
            integration=runtime.integration,
            provider=runtime.provider,
            model=runtime.model,
        )
    )
    capture = root / "conformance" / f"{phase}-raw.txt"
    session = workspace.start_session(
        StartSessionInput(
            id=session_id,
            actor_id=actor_id,
            swarm_id="delivery",
            work_id="increment",
            runner=_runner(runtime.integration, phase, capture),
            launch=True,
        )
    )
    return session, normalize_output(runtime.integration, capture.read_text(encoding="utf-8"))


def _record_evidence(
    workspace: AgoraWorkspace,
    root: Path,
    *,
    actor_id: str,
    artifact_actor_id: str,
    phase: str,
    normalized: dict,
) -> None:
    path = root / "conformance" / f"{phase}.json"
    path.write_text(json.dumps(normalized, sort_keys=True) + "\n", encoding="utf-8")
    uri = f"repo://conformance/{phase}.json"
    workspace.add_artifact(
        AddArtifactInput(
            swarm_id="delivery",
            work_id="increment",
            actor_id=artifact_actor_id,
            kind=f"{phase}-output",
            uri=uri,
        )
    )
    workspace.add_evidence(
        AddEvidenceInput(
            swarm_id="delivery",
            work_id="increment",
            actor_id=actor_id,
            type=f"runtime-conformance-{phase}",
            result="success",
            artifact_refs=[uri],
            environment="offline-fake-runner",
            exit_code=0,
        )
    )


def _observed(actor: str, runtime: RuntimeSpec, subject: ArtifactRevision):
    def value(item: str) -> dict[str, str]:
        return {"value": item, "source": "observed"}

    return parse(
        {
            "schema": "agora-ai-sdlc/provenance/v1",
            "actor": actor,
            "runtime": value(runtime.integration),
            "runtime_version": value("fake-1.0"),
            "provider": value(runtime.provider),
            "model": value(runtime.model),
            "selection_reason": value("conformance matrix"),
            "fallback": {"source": "observed", "used": False},
            "subject": {
                "kind": subject.kind,
                "id": subject.id,
                "revision": subject.revision,
                "digest": subject.digest,
            },
        }
    )


def _profile_results(
    producer_session,
    reviewer_session,
    producer_runtime: RuntimeSpec,
    reviewer_runtime: RuntimeSpec,
    reviewer_kind: str,
) -> dict[str, bool]:
    results = {}
    for profile in ("distinct-actor", "distinct-runtime", "distinct-provider", "human-final", "regulated"):
        subject = ArtifactRevision("architecture", "ARC-001", 1, "sha256:conformance", (profile,))
        producer = _observed(producer_session.executor or producer_session.actor, producer_runtime, subject)
        reviewer_provenance = _observed(
            reviewer_session.executor or reviewer_session.actor,
            reviewer_runtime,
            subject,
        )
        review = Review(
            actor=reviewer_provenance.actor,
            actor_kind=reviewer_kind,
            role="quality-reviewer",
            subject=subject,
            verdict="approved",
            provenance=reviewer_provenance,
        )
        results[profile] = evaluate_review(produced=subject, producer=producer, review=review)["allowed"]
    return results


def run_case(root: Path, case: dict) -> dict:
    producer_runtime = RuntimeSpec(**case["producer"]["runtime"])
    reviewer_runtime = RuntimeSpec(**case["reviewer"]["runtime"])
    same_actor = case["producer"]["actor"] == case["reviewer"]["actor"]
    workspace = _workspace(root, case["reviewer"]["kind"], same_actor)

    producer_session, production = _session(
        workspace,
        root,
        session_id="production-session",
        actor_id=case["producer"]["actor"],
        runtime=producer_runtime,
        phase="production",
    )
    reviewer_session, review = _session(
        workspace,
        root,
        session_id="review-session",
        actor_id=case["reviewer"]["actor"],
        runtime=reviewer_runtime,
        phase="review",
    )
    producer_actor_id = case["producer"]["actor"]
    _record_evidence(
        workspace,
        root,
        actor_id=producer_actor_id,
        artifact_actor_id=producer_actor_id,
        phase="production",
        normalized=production,
    )
    _record_evidence(
        workspace,
        root,
        actor_id=case["reviewer"]["actor"],
        artifact_actor_id=producer_actor_id,
        phase="review",
        normalized=review,
    )

    producer_provenance = _observed(
        producer_session.executor or producer_session.actor,
        producer_runtime,
        ArtifactRevision("architecture", "ARC-001", 1, "sha256:conformance", ("distinct-actor",)),
    )
    data = evaluate_launch(
        inputs=[ClassifiedInput("requirements", "internal", 1)],
        runtime=producer_provenance,
        execution_boundary=Value("customer-controlled", "observed"),
        eligibility=RuntimeEligibility(
            producer_runtime.integration,
            "restricted",
            ("customer-controlled",),
            1,
            "conformance fixture",
        ),
    )
    selection = select_runtime(
        Route(
            "implementation",
            (
                Candidate(
                    RuntimeRef("producer", **case["producer"]["runtime"]),
                    {},
                    data,
                    {"allowed": True, "blockers": []},
                ),
            ),
        )
    )
    evidence = workspace.list_work_evidence("delivery", "increment")
    snapshot = {
        "sessions": [
            {"phase": "production", "status": producer_session.status, "exit_code": producer_session.exit_code},
            {"phase": "review", "status": reviewer_session.status, "exit_code": reviewer_session.exit_code},
        ],
        "outputs": [production, review],
        "evidence": [
            {
                "type": item.type,
                "result": item.result,
                "artifact": Path(item.artifact_references[0]).name,
            }
            for item in evidence
        ],
        "work": {"state": workspace.show_work("delivery", "increment").state, "evidence_count": len(evidence)},
    }
    return {
        "snapshot": snapshot,
        "profiles": _profile_results(
            producer_session,
            reviewer_session,
            producer_runtime,
            reviewer_runtime,
            case["reviewer"]["kind"],
        ),
        "data_allowed": data["allowed"],
        "selection_allowed": selection["allowed"],
        "session_runtimes": [
            [producer_session.integration, producer_session.provider, producer_session.model],
            [reviewer_session.integration, reviewer_session.provider, reviewer_session.model],
        ],
    }
