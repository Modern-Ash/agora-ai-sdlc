"""Drive a real Agora Core workspace with the AI-SDLC pack (credential-free, local only)."""

import json
import subprocess
from pathlib import Path

from agora.model import (
    AddActorInput,
    AddApprovalInput,
    AddArtifactInput,
    AddEvidenceInput,
    AssignActorInput,
    ConfigureInput,
    CreateSwarmInput,
    CreateWorkInput,
    InitInput,
    InstallMethodInput,
    ReopenWorkInput,
    TransitionWorkInput,
    WorkActorInput,
)
from agora.workspace import AgoraWorkspace

PACK = Path(__file__).parent.parent.parent / "registry" / "methods" / "ai-sdlc"
# role -> (actor id, kind, capabilities)
ACTORS = {
    "product-owner": ("po", "human", ["specification"]),
    "architect": ("arch", "ai-agent", ["specification"]),
    "builder": ("build", "ai-agent", ["implementation"]),
    "operator": ("ops", "ai-agent", ["operations"]),
    "quality-reviewer": ("qa", "human", ["review"]),
}
SWARM, WORK = "delivery", "feature"


class Lifecycle:
    def __init__(self, root: Path, home: Path, monkeypatch) -> None:
        monkeypatch.setenv("AGORA_HOME", str(home))
        subprocess.run(["git", "init", "-q", str(root)], check=True)

        def advisory(command, cwd, environment):
            return subprocess.CompletedProcess(command, 0, json.dumps({"questions": []}), "")

        self.root = root
        self.ws = AgoraWorkspace(cwd=root, tool_runner=advisory)
        self.ws.configure(
            ConfigureInput(integration="generic", provider="local", model="local", default_method="scrum")
        )
        self.ws.initialize(InitInput())
        self.ws.install_method(InstallMethodInput(source=str(PACK), scope="project"))
        for actor_id, kind, caps in ACTORS.values():
            self.ws.add_actor(AddActorInput(id=actor_id, name=actor_id, kind=kind, capabilities=caps, scope="project"))
        self.ws.create_swarm(CreateSwarmInput(id=SWARM, objective="AI-SDLC", method="ai-sdlc", create_branch=False))
        for role, (actor_id, _kind, _caps) in ACTORS.items():
            self.ws.assign_actor(AssignActorInput(swarm_id=SWARM, role_id=role, actor_id=actor_id))
        self.ws.create_work(
            CreateWorkInput(
                swarm_id=SWARM, id=WORK, title="Sample", actor_id="po",
                acceptance_criteria=[("value", "Delivers value")], required_artifacts=[],
            )
        )  # fmt: skip

    def wa(self, actor: str) -> WorkActorInput:
        return WorkActorInput(swarm_id=SWARM, work_id=WORK, actor_id=actor)

    def artifact(self, actor: str, kind: str) -> None:
        (self.root / f"{kind}.md").write_text(f"# {kind}\n", encoding="utf-8")
        self.ws.add_artifact(
            AddArtifactInput(swarm_id=SWARM, work_id=WORK, actor_id=actor, kind=kind, uri=f"repo://{kind}.md")
        )

    def approve(self, actor: str, role: str) -> None:
        self.ws.add_approval(AddApprovalInput(swarm_id=SWARM, work_id=WORK, actor_id=actor, role_id=role, note="ok"))

    def evidence(self, actor: str, kind: str) -> None:
        self.ws.add_evidence(
            AddEvidenceInput(
                swarm_id=SWARM, work_id=WORK, actor_id=actor, type=kind, result="success",
                artifact_refs=["repo://readiness-assessment.md"],
            )
        )  # fmt: skip

    def stage(self, actor: str, stage: str) -> None:
        self.ws.satisfy_criterion(self.wa(actor), "value", stage=stage)

    def move(self, actor: str, target: str) -> str:
        return self.ws.transition_work(
            TransitionWorkInput(swarm_id=SWARM, work_id=WORK, actor_id=actor, target_state=target)
        ).state

    def state(self) -> str:
        return self.ws.show_work(SWARM, WORK).state

    def reopen(self, actor: str, reason: str):
        return self.ws.reopen_work(ReopenWorkInput(swarm_id=SWARM, work_id=WORK, actor_id=actor, reason=reason))

    # Phase helpers: satisfy each gate's prerequisites, then move.
    def to_intent(self) -> None:
        self.artifact("po", "readiness-assessment")
        self.ws.clarify_work(self.wa("po"), runner="/bin/true")
        self.approve("po", "product-owner")
        assert self.move("po", "intent") == "intent"

    def clarify(self, actor: str = "po") -> None:
        self.ws.clarify_work(self.wa(actor), runner="/bin/true")

    def to_inception(self) -> None:
        self.stage("po", "elaborated")
        self.artifact("po", "intent")
        self.approve("po", "product-owner")
        self.clarify()
        assert self.move("po", "inception") == "inception"

    def to_construction(self) -> None:
        self.stage("arch", "designed")
        self.artifact("arch", "architecture")
        self.artifact("arch", "requirements")
        self.approve("arch", "architect")
        self.approve("po", "product-owner")
        self.clarify()
        assert self.move("arch", "construction") == "construction"

    def to_operations(self) -> None:
        self.stage("build", "built")
        self.stage("qa", "verified")
        self.artifact("build", "implementation")
        self.artifact("build", "test-strategy")
        self.evidence("build", "test-suite")
        self.approve("qa", "quality-reviewer")
        assert self.move("qa", "operations") == "operations"

    def prepare_completion(self, skip: str | None = None) -> None:
        for kind in ("deployment-plan", "rollback-procedure", "operational-readiness"):
            if skip != kind:
                self.artifact("ops", kind)
        if skip != "criterion":
            self.stage("ops", "deployed")
            self.stage("po", "accepted")
        if skip != "deployment":
            self.evidence("ops", "deployment")
        if skip != "security-scan":
            self.evidence("ops", "security-scan")
        if skip != "approval":
            self.approve("po", "product-owner")

    def to_completed(self) -> None:
        self.prepare_completion()
        assert self.move("po", "completed") == "completed"
