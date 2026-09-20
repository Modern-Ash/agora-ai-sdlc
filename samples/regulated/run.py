"""Credential-free Regulated profile sample: signed critical actions, segregation and audit metadata.

Every actor signs with an ephemeral in-memory Ed25519 key; Agora Core verifies each signature. Prints a
machine-checkable JSON summary. Run with: agora-ai-sdlc run-sample regulated
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agora.identity import lifecycle_authorization_payload
from agora.model import (
    AddActorInput,
    AssignActorInput,
    ConfigureInput,
    CreateSwarmInput,
    CreateWorkInput,
    InitInput,
    InstallMethodInput,
    PrepareApprovalInput,
    PrepareArtifactInput,
    PrepareCreateWorkInput,
    PrepareCriterionInput,
    PrepareEvidenceInput,
    PrepareWorkTransitionInput,
    WorkActorInput,
)
from agora.workspace import AgoraWorkspace
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.provenance import parse
from agora_ai_sdlc.regulated import (
    EvidenceRetention,
    ExceptionRecord,
    RegulatedError,
    apply_signed_action,
    assign_actor,
    evaluate_ai_execution,
    prepare_evidence,
    prepare_transition,
    record_exception,
)

PACK = asset_root("registry") / "methods" / "ai-sdlc"
SWARM, WORK = "delivery", "feature"
ACTORS = {
    "product-owner": ("po", "human", ["specification"]),
    "architect": ("arch", "ai-agent", ["specification"]),
    "builder": ("build", "ai-agent", ["implementation"]),
    "operator": ("ops", "ai-agent", ["operations"]),
    "quality-reviewer": ("qa", "human", ["review"]),
}
AUTHORIZERS = {"project:governance": "governance-owner"}


def provenance(source: str):
    return parse(
        {
            "schema": "agora-ai-sdlc/provenance/v1",
            "actor": "project:builder",
            "runtime": {"value": "runner", "source": source},
            "runtime_version": {"value": "1.2.3", "source": source},
            "provider": {"value": "provider", "source": source},
            "model": {"value": "model", "source": source},
            "selection_reason": {"value": "approved-route", "source": source},
            "fallback": {"source": source, "used": False},
        }
    )


class Regulated:
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self.root = workdir / "project"
        os.environ["AGORA_HOME"] = str(workdir / "home")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

        def advisory(command, cwd, environment):
            return subprocess.CompletedProcess(command, 0, json.dumps({"questions": []}), "")

        self.ws = AgoraWorkspace(cwd=self.root, tool_runner=advisory)
        self.ws.configure(ConfigureInput("generic", "local", "local", "scrum"))
        self.ws.initialize(InitInput())
        self.ws.install_method(InstallMethodInput(source=str(PACK), scope="project"))
        self.keys: dict[str, Ed25519PrivateKey] = {}
        for actor_id, kind, capabilities in ACTORS.values():
            private = Ed25519PrivateKey.generate()
            public = workdir / f"{actor_id}.pem"
            public.write_bytes(
                private.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            self.ws.add_actor(
                AddActorInput(
                    id=actor_id,
                    name=actor_id,
                    kind=kind,
                    capabilities=capabilities,
                    scope="project",
                    public_key=str(public),
                    require_authentication=True,
                )
            )
            self.keys[actor_id] = private
        self.ws.create_swarm(CreateSwarmInput(SWARM, "Regulated delivery", method="ai-sdlc", create_branch=False))
        for role, (actor_id, _kind, _caps) in ACTORS.items():
            assign_actor(self.ws, AssignActorInput(SWARM, role, actor_id))
        self.signed = 0
        self.counter = 0

    def next_id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}-{self.counter:02d}"

    def sign_apply(self, action, actor: str) -> None:
        path = self.workdir / f"{action.id}.sig"
        path.write_bytes(self.keys[actor].sign(lifecycle_authorization_payload(action)))
        applied = apply_signed_action(self.ws, action.id, str(path))
        assert applied.status == "applied" and applied.authentication_verified
        self.signed += 1

    def wa(self, actor: str) -> WorkActorInput:
        return WorkActorInput(swarm_id=SWARM, work_id=WORK, actor_id=actor)

    def create_work(self) -> None:
        work = CreateWorkInput(
            swarm_id=SWARM, id=WORK, title="Regulated change", actor_id="po",
            acceptance_criteria=[("value", "Delivers value")], required_artifacts=[],
        )  # fmt: skip
        self.sign_apply(self.ws.prepare_create_work(PrepareCreateWorkInput("create-feature", work)), "po")

    def artifact(self, actor: str, kind: str) -> None:
        (self.root / f"{kind}.md").write_text(f"# {kind}\n", encoding="utf-8")
        action = self.ws.prepare_add_artifact(
            PrepareArtifactInput(SWARM, WORK, actor, kind, f"repo://{kind}.md", id=self.next_id("artifact"))
        )
        self.sign_apply(action, actor)

    def approve(self, actor: str, role: str) -> None:
        action = self.ws.prepare_approval(
            PrepareApprovalInput(SWARM, WORK, actor, role_id=role, note="ok", id=self.next_id("approval"))
        )
        self.sign_apply(action, actor)

    def stage(self, actor: str, stage: str) -> None:
        action = self.ws.prepare_satisfy_criterion(
            PrepareCriterionInput(SWARM, WORK, actor, id=self.next_id("criterion"), criterion_id="value", stage=stage)
        )
        self.sign_apply(action, actor)

    def evidence(self, actor: str, kind: str) -> None:
        evidence_id = self.next_id("evidence")
        now = datetime.now(UTC)
        retention = EvidenceRetention(
            id=evidence_id,
            evidence_ref=evidence_id,
            owner="project:qa",
            classification="internal",
            policy="quality-evidence-7-years",
            recorded_at=(now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            retain_until=(now + timedelta(days=2555)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            disposition="review",
        )
        data = PrepareEvidenceInput(
            SWARM, WORK, actor, type=kind, result="success",
            artifact_refs=["repo://readiness-assessment.md"], id=evidence_id,
        )  # fmt: skip
        self.sign_apply(prepare_evidence(self.ws, data, retention, now=now), actor)

    def clarify(self, actor: str = "po") -> None:
        action = self.ws.prepare_work_clarification(self.next_id("clarification"), self.wa(actor), runner="/bin/true")
        self.sign_apply(action, actor)

    def move(self, actor: str, target: str) -> str:
        action = prepare_transition(
            self.ws, PrepareWorkTransitionInput(SWARM, WORK, actor, target, id=self.next_id("transition"))
        )
        self.sign_apply(action, actor)
        return self.state()

    def state(self) -> str:
        return self.ws.show_work(SWARM, WORK).state

    def lifecycle(self) -> None:
        self.artifact("po", "readiness-assessment")
        self.clarify()
        self.approve("po", "product-owner")
        assert self.move("po", "intent") == "intent"
        self.stage("po", "elaborated")
        self.artifact("po", "intent")
        self.approve("po", "product-owner")
        self.clarify()
        assert self.move("po", "inception") == "inception"
        self.stage("arch", "designed")
        self.artifact("arch", "architecture")
        self.artifact("arch", "requirements")
        self.approve("arch", "architect")
        self.approve("po", "product-owner")
        self.clarify()
        assert self.move("arch", "construction") == "construction"
        self.stage("build", "built")
        self.stage("qa", "verified")
        self.artifact("build", "implementation-plan")
        self.artifact("build", "test-strategy")
        self.evidence("build", "test-suite")
        self.approve("qa", "quality-reviewer")
        assert self.move("qa", "operations") == "operations"
        for kind in ("deployment-plan", "rollback-procedure", "operational-readiness"):
            self.artifact("ops", kind)
        self.stage("ops", "deployed")
        self.stage("po", "accepted")
        self.evidence("ops", "deployment")
        self.evidence("ops", "security-scan")
        self.approve("po", "product-owner")
        assert self.move("po", "completed") == "completed"


def code(error: BaseException) -> str:
    return getattr(error, "code", type(error).__name__)


def main() -> dict:
    workdir = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-regulated-"))
    sample = Regulated(workdir)
    ws = sample.ws
    rejected: dict[str, str] = {}

    # 1. an unsigned critical mutation is refused by Core
    try:
        ws.create_work(CreateWorkInput(swarm_id=SWARM, id="unsigned", title="Unsigned", actor_id="po"))
    except PermissionError as error:
        rejected["unsigned_mutation"] = (
            "signed-lifecycle-action-required" if "signed lifecycle action" in str(error) else str(error)
        )
    else:
        raise AssertionError("an unsigned critical mutation must be rejected")

    # 2. segregation and human-role checks fail before any assignment
    robot = AddActorInput("robot", "robot", "ai-agent", ["specification"], "project")
    ws.add_actor(robot)
    ws.create_swarm(CreateSwarmInput("probe", "Assignment probe", method="ai-sdlc", create_branch=False))
    try:
        assign_actor(ws, AssignActorInput("probe", "product-owner", "robot"))
    except RegulatedError as error:
        rejected["non_human_product_owner"] = code(error)
    shared_key = sample.workdir / "shared.pem"
    shared_key.write_bytes(
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    ws.add_actor(
        AddActorInput(
            "shared",
            "shared",
            "human",
            ["implementation", "review"],
            "project",
            public_key=str(shared_key),
            require_authentication=True,
        )
    )
    assign_actor(ws, AssignActorInput("probe", "builder", "shared"))
    try:
        assign_actor(ws, AssignActorInput("probe", "quality-reviewer", "shared"))
    except RegulatedError as error:
        rejected["builder_reviewer_combination"] = code(error)

    # 3. AI execution needs complete observed provenance
    provenance_gate = {
        "declared": evaluate_ai_execution(provenance("declared"))["allowed"],
        "observed": evaluate_ai_execution(provenance("observed"))["allowed"],
    }

    # 4. exceptions are authorized, time-bound and cannot waive non-waivable controls
    now = datetime.now(UTC)
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    exception = ExceptionRecord(
        id="temporary-control", policy="operational-control",
        reason="Compensating manual review is active", authorized_by="project:governance",
        authorized_role="governance-owner", created_at=(now - timedelta(minutes=5)).strftime(stamp),
        expires_at=(now + timedelta(days=1)).strftime(stamp), evidence="repo://evidence/approval-17",
    )  # fmt: skip
    for label, changes in (
        ("unauthorized_exception", {"authorized_by": "project:unknown"}),
        ("non_waivable_exception", {"policy": "role-segregation"}),
    ):
        try:
            record_exception(
                sample.root, ExceptionRecord(**{**exception.__dict__, **changes}), authorizers=AUTHORIZERS, now=now
            )
        except RegulatedError as error:
            rejected[label] = code(error)
    exception_path = record_exception(sample.root, exception, authorizers=AUTHORIZERS, now=now)

    # 5. the full lifecycle: every critical action is signed and verified by Core
    sample.create_work()
    sample.lifecycle()

    validated = subprocess.run(
        [sys.executable, "-m", "agora", "validate"], cwd=sample.root, capture_output=True, text=True, check=False
    )
    audit_root = sample.root / ".agora" / "regulated"
    summary = {
        "sample": "regulated",
        "final_state": sample.state(),
        "signed_actions": sample.signed,
        "rejected": rejected,
        "provenance_gate": provenance_gate,
        "exception_recorded": exception_path.is_file(),
        "retention_records": len(list((audit_root / "evidence-retention").glob("*.json"))),
        "validate": "ok" if validated.returncode == 0 else "failed",
    }
    if summary["final_state"] == "completed" and summary["validate"] == "ok":
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        summary["workspace"] = str(workdir)
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
