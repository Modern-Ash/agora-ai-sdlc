"""Credential-free incremental modernization scenario over the Core lifecycle."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from agora.model import AddArtifactInput, AddEvidenceInput, TransitionWorkInput

from agora_ai_sdlc.artifacts import parse_artifact
from agora_ai_sdlc.modernization import ModernizationError, transition
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle

HERE = Path(__file__).parent


class ModernizationLifecycle(Lifecycle):
    def move(self, actor: str, target: str) -> str:
        return transition(
            self.ws,
            TransitionWorkInput(swarm_id=SWARM, work_id=WORK, actor_id=actor, target_state=target),
        ).state


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-modernization-"))
    project = runtime / "project"
    life = ModernizationLifecycle(project, runtime / "home")
    registered: dict[str, str] = {}
    blocked: list[str] = []

    def artifact(name: str, actor: str) -> None:
        source = HERE / "fixtures" / f"{name}.md"
        destination = project / "modernization" / source.name
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, destination)
        parsed = parse_artifact(destination.read_text(encoding="utf-8"))
        uri = f"repo://modernization/{source.name}"
        life.ws.add_artifact(AddArtifactInput(SWARM, WORK, actor, parsed.kind, uri))
        registered[name] = uri

    def evidence(actor: str, type_: str, artifact_name: str, result: str = "success") -> None:
        life.ws.add_evidence(
            AddEvidenceInput(
                swarm_id=SWARM,
                work_id=WORK,
                actor_id=actor,
                type=type_,
                result=result,
                artifact_refs=[registered[artifact_name]],
            )
        )

    for name in ("legacy-inventory", "dependency-map", "characterization"):
        artifact(name, "po")
    life.to_intent()
    life.to_inception()

    for name in ("target-architecture", "migration-plan", "migration-slice"):
        artifact(name, "arch")
    life.to_construction()

    artifact("conversion-record", "build")
    artifact("equivalence-failed", "qa")
    evidence("qa", "behavioral-equivalence", "equivalence-failed", result="failure")
    life.stage("build", "built")
    life.stage("qa", "verified")
    life.artifact("build", "implementation-plan")
    life.artifact("build", "test-strategy")
    life.evidence("build", "test-suite")
    life.approve("qa", "quality-reviewer")
    try:
        life.move("qa", "operations")
    except ModernizationError as error:
        blocked.append(error.code)
    else:
        raise AssertionError("failed equivalence must block operations")

    artifact("equivalence-passed", "qa")
    evidence("qa", "behavioral-equivalence", "equivalence-passed")
    assert life.move("qa", "operations") == "operations"

    artifact("cutover-plan", "ops")
    artifact("stabilization-report", "ops")
    evidence("ops", "cutover", "cutover-plan")
    evidence("ops", "stabilization", "stabilization-report")
    life.prepare_completion()
    try:
        life.move("po", "completed")
    except ModernizationError as error:
        blocked.append(error.code)
    else:
        raise AssertionError("missing rollback validation must block completion")

    registered["rollback-procedure"] = "repo://rollback-procedure.md"
    evidence("ops", "rollback-validation", "rollback-procedure")
    assert life.move("po", "completed") == "completed"

    validated = subprocess.run(
        [sys.executable, "-m", "agora", "validate"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    summary = {
        "final_state": life.state(),
        "validate": "ok" if validated.returncode == 0 else "failed",
        "profile": "modernization",
        "slice_ids": ["checkout-total"],
        "known_behaviors": ["priced-cart"],
        "unknown_behaviors": ["empty-cart-rounding"],
        "blocked_paths": blocked,
        "accepted_difference": "empty-cart-rounding",
        "rollback_validated": True,
    }
    print(json.dumps(summary, sort_keys=True))
    if summary["final_state"] == "completed" and summary["validate"] == "ok":
        shutil.rmtree(runtime)
    else:
        summary["workspace"] = str(project)
    return summary


if __name__ == "__main__":
    main()
