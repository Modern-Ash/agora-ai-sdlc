"""End-to-end adaptive AI-SDLC 0.2.0 sample, offline and credential-free."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from agora.model import AddArtifactInput, AddEvidenceInput

from agora_ai_sdlc.bolts import parse_bolt_plan, ready_bolts, trace
from agora_ai_sdlc.context_graph import context_bundle, graph_from_directory
from agora_ai_sdlc.plans import assert_executable, parse_plan, validate_plan_graph
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle


def artifact_doc(kind: str, artifact_id: str, traces: tuple[str, ...] = ()) -> str:
    traces_yaml = "[" + ", ".join(f'"{item}"' for item in traces) + "]"
    return (
        "---\n"
        'schema: "agora-ai-sdlc/artifact/v1"\n'
        f'kind: "{kind}"\n'
        "version: 1\n"
        f'id: "{artifact_id}"\n'
        f'work: "{WORK}"\n'
        "revision: 1\n"
        f"traces-to: {traces_yaml}\n"
        'required-sections: ["Section"]\n'
        "---\n"
        f"# {kind}\n\n## Section\n\n{kind} evidence.\n"
    )


LEVEL1 = """---
schema: "agora-ai-sdlc/artifact/v1"
kind: "plan"
version: 1
id: "PLN-001"
work: "feature"
revision: 1
traces-to: ["INT-001", "UOW-001"]
level: 1
parent-plan: null
intent: "INT-001"
unit: "UOW-001"
proposed-by: "project:planner"
approval-state: "approved"
approved-by: "project:po"
approved-revision: 1
steps:
  - id: "elaborate"
    decision: "execute"
    rationale: "Requirements must be elaborated."
    dependencies: []
    required-artifacts: ["intent", "unit-of-work"]
    produced-artifacts: ["requirements"]
  - id: "design"
    decision: "execute"
    rationale: "Design follows approved requirements."
    dependencies: ["elaborate"]
    required-artifacts: ["requirements"]
    produced-artifacts: ["domain-model", "architecture"]
required-sections: ["Scope", "Level and parent", "Steps", "Approval"]
---
# Plan

## Scope

Intent INT-001 / Unit UOW-001.

## Level and parent

Level 1.

## Steps

Elaborate then design.

## Approval

Approved revision 1.
"""

LEVEL2 = """---
schema: "agora-ai-sdlc/artifact/v1"
kind: "plan"
version: 1
id: "PLN-002"
work: "feature"
revision: 1
traces-to: ["INT-001", "UOW-001", "PLN-001"]
level: 2
parent-plan: "PLN-001"
intent: "INT-001"
unit: "UOW-001"
proposed-by: "project:planner"
approval-state: "approved"
approved-by: "project:po"
approved-revision: 1
steps:
  - id: "logical-design"
    decision: "execute"
    rationale: "Detail the design."
    dependencies: []
    required-artifacts: ["requirements"]
    produced-artifacts: ["architecture"]
  - id: "optional-spike"
    decision: "skip"
    rationale: "Existing evidence makes the spike unnecessary."
    dependencies: ["logical-design"]
    required-artifacts: ["architecture"]
    produced-artifacts: []
required-sections: ["Scope", "Level and parent", "Steps", "Approval"]
---
# Plan

## Scope

Intent INT-001 / Unit UOW-001.

## Level and parent

Level 2 child of PLN-001.

## Steps

Design with one justified skip.

## Approval

Approved revision 1.
"""


def bolt_plan(*, completed: bool) -> str:
    api_status = "completed" if completed else "approved"
    ui_status = "completed" if completed else "approved"
    integrate_status = "completed" if completed else "approved"
    api_evidence = '["evidence:api-tests"]' if completed else "[]"
    ui_evidence = '["evidence:ui-tests"]' if completed else "[]"
    integrate_evidence = '["evidence:e2e-tests"]' if completed else "[]"
    return f"""---
schema: "agora-ai-sdlc/artifact/v1"
kind: "bolt-plan"
version: 1
id: "BLP-001"
work: "feature"
revision: 1
traces-to: ["UOW-001", "PLN-001"]
unit: "UOW-001"
plan: "PLN-001"
proposed-by: "project:planner"
approval-state: "approved"
approved-by: "project:po"
approved-revision: 1
bolts:
  - id: "schema"
    mode: "sequential"
    status: "completed"
    tasks: ["Define storage schema"]
    depends-on: []
    writes: ["src/schema/"]
    produces: ["IMP-001"]
    evidence: ["evidence:schema-tests"]
  - id: "api"
    mode: "parallel"
    status: "{api_status}"
    tasks: ["Implement API"]
    depends-on: ["schema"]
    writes: ["src/api/"]
    produces: []
    evidence: {api_evidence}
  - id: "ui"
    mode: "parallel"
    status: "{ui_status}"
    tasks: ["Implement UI"]
    depends-on: ["schema"]
    writes: ["src/ui/"]
    produces: []
    evidence: {ui_evidence}
  - id: "integrate"
    mode: "sequential"
    status: "{integrate_status}"
    tasks: ["Integrate and verify"]
    depends-on: ["schema", "api", "ui"]
    writes: ["tests/e2e/"]
    produces: []
    evidence: {integrate_evidence}
required-sections: ["Scope", "Bolts", "Conflicts", "Approval"]
---
# Bolt Plan

## Scope

Unit UOW-001.

## Bolts

API and UI may execute in parallel after schema.

## Conflicts

Parallel writes are disjoint.

## Approval

Approved revision 1.
"""


def register(life: Lifecycle, actor: str, kind: str, name: str, contents: str) -> None:
    path = life.root / name
    path.write_text(contents, encoding="utf-8")
    life.ws.add_artifact(
        AddArtifactInput(
            swarm_id=SWARM,
            work_id=WORK,
            actor_id=actor,
            kind=kind,
            uri=f"repo://{name}",
        )
    )


def evidence(life: Lifecycle, actor: str, kind: str, artifact: str) -> None:
    life.ws.add_evidence(
        AddEvidenceInput(
            swarm_id=SWARM,
            work_id=WORK,
            actor_id=actor,
            type=kind,
            result="success",
            artifact_refs=[f"repo://{artifact}"],
        )
    )


def main() -> dict:
    workdir = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-adaptive-"))
    project = workdir / "project"
    life = Lifecycle(project, workdir / "home", method_version="0.2.0")

    # Inception: durable Intent/Unit and approved recursive plan hierarchy.
    register(life, "po", "intent", "intent.md", artifact_doc("intent", "INT-001"))
    register(life, "po", "unit-of-work", "unit.md", artifact_doc("unit-of-work", "UOW-001", ("INT-001",)))
    register(life, "po", "requirements", "requirements.md", artifact_doc("requirements", "REQ-001", ("UOW-001",)))
    register(life, "po", "user-stories", "user-stories.md", artifact_doc("user-stories", "UST-001", ("REQ-001",)))
    register(life, "po", "nfr", "nfr.md", artifact_doc("nfr", "NFR-001", ("REQ-001",)))
    register(life, "po", "risk-register", "risk-register.md", artifact_doc("risk-register", "RSK-001", ("NFR-001",)))
    register(
        life,
        "po",
        "measurement-criteria",
        "measurement-criteria.md",
        artifact_doc("measurement-criteria", "MCR-001", ("UST-001",)),
    )
    register(life, "po", "bolt-plan", "bolt-plan-draft.md", bolt_plan(completed=False))

    level1 = parse_plan(LEVEL1)
    level2 = parse_plan(LEVEL2)
    assert_executable(level1)
    assert_executable(level2)
    validate_plan_graph([level1, level2])
    register(life, "po", "plan", "plan-level1.md", LEVEL1)
    register(life, "po", "plan", "plan-level2.md", LEVEL2)

    life.stage("po", "elaborated")
    life.clarify("po")
    life.approve("po", "product-owner")
    life.approve("dev", "developer")
    assert life.move("dev", "construction") == "construction"

    # Construction: demonstrate two parallel-ready Bolts, then persist complete Bolt evidence.
    ready_plan = parse_bolt_plan(bolt_plan(completed=False))
    parallel_ready = ready_bolts(ready_plan)
    assert parallel_ready == ("api", "ui")

    final_bolts = parse_bolt_plan(bolt_plan(completed=True))
    bolt_summary = trace(final_bolts)
    assert bolt_summary["construction_evidence_complete"]
    (project / "bolt-plan-draft.md").write_text(bolt_plan(completed=True), encoding="utf-8")

    register(life, "dev", "domain-model", "domain-model.md", artifact_doc("domain-model", "DOM-001", ("UOW-001",)))
    register(life, "dev", "architecture", "architecture.md", artifact_doc("architecture", "ARC-001", ("REQ-001",)))
    register(
        life,
        "dev",
        "logical-design",
        "logical-design.md",
        artifact_doc("logical-design", "LOG-001", ("DOM-001", "NFR-001", "RSK-001")),
    )
    register(
        life,
        "dev",
        "implementation-plan",
        "implementation-plan.md",
        artifact_doc("implementation-plan", "IMP-001", ("LOG-001",)),
    )
    register(
        life,
        "dev",
        "test-strategy",
        "test-strategy.md",
        artifact_doc("test-strategy", "TST-001", ("UST-001", "NFR-001")),
    )
    register(
        life,
        "dev",
        "deployment-unit",
        "deployment-unit.md",
        artifact_doc("deployment-unit", "DPU-001", ("IMP-001", "TST-001", "LOG-001")),
    )

    # Unrelated artifact proves context scoping.
    (project / "unrelated.md").write_text(artifact_doc("intent", "INT-999"), encoding="utf-8")
    graph = graph_from_directory(project)
    bundle = context_bundle(graph, "UOW-001")
    context_ids = [item.id for item in bundle.items]
    assert "PLN-001" in context_ids and "BLP-001" in context_ids
    assert "INT-999" not in context_ids

    life.stage("dev", "designed")
    life.stage("dev", "built")
    life.stage("dev", "verified")
    evidence(life, "dev", "test-suite", "test-strategy.md")
    life.approve("dev", "developer")
    assert life.move("dev", "operations") == "operations"

    # Operations and accountable completion.
    register(
        life,
        "dev",
        "operational-readiness",
        "operational-readiness.md",
        artifact_doc("operational-readiness", "OPR-001", ("UOW-001",)),
    )
    register(
        life,
        "dev",
        "rollback-procedure",
        "rollback-procedure.md",
        artifact_doc("rollback-procedure", "RBK-001", ("UOW-001",)),
    )
    life.stage("dev", "deployed")
    life.stage("po", "accepted")
    evidence(life, "dev", "deployment", "operational-readiness.md")
    evidence(life, "dev", "security-scan", "operational-readiness.md")
    life.approve("po", "product-owner")
    assert life.move("po", "completed") == "completed"

    validated = subprocess.run(
        [sys.executable, "-m", "agora", "validate"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    summary = {
        "sample": "adaptive-delivery",
        "method_version": life.method_version,
        "final_state": life.state(),
        "recursive_plan": {
            "level1": level1.artifact.id,
            "level2": level2.artifact.id,
            "parent": level2.parent_plan,
            "approved": True,
        },
        "parallel_ready_bolts": list(parallel_ready),
        "construction_evidence_complete": bolt_summary["construction_evidence_complete"],
        "context_root": bundle.root,
        "context_ids": context_ids,
        "unrelated_excluded": "INT-999" not in context_ids,
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
