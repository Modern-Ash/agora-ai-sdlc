"""Credential-free GitHub delivery profile sample."""

import json
import shutil
import tempfile
from pathlib import Path

from agora.model import AddArtifactInput, AddEvidenceInput, InvokeToolInput

from agora_ai_sdlc.github_delivery import (
    authorize_operation,
    ingest_snapshot,
    install_read_only,
    normalize_delivery,
)
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle

HERE = Path(__file__).parent


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-github-delivery-"))
    project = runtime / "project"
    lifecycle = Lifecycle(project, runtime / "home")
    try:
        adapters = install_read_only(lifecycle.ws, project)
        fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
        snapshot = normalize_delivery(**fixture)
        observations, created = ingest_snapshot((), snapshot)
        observations, duplicate_created = ingest_snapshot(observations, snapshot)

        prepared = [
            lifecycle.ws.invoke_tool(
                InvokeToolInput(
                    id="github-issue-read",
                    tool_id="github-issues",
                    operation_id="view",
                    actor_id="po",
                    swarm_id=SWARM,
                    work_id=WORK,
                    inputs={"issue": "42"},
                    read_only_sync=True,
                )
            ),
            lifecycle.ws.invoke_tool(
                InvokeToolInput(
                    id="github-pr-read",
                    tool_id="github-pull-requests",
                    operation_id="view",
                    actor_id="build",
                    swarm_id=SWARM,
                    work_id=WORK,
                    inputs={"review": "56"},
                    read_only_sync=True,
                )
            ),
            lifecycle.ws.invoke_tool(
                InvokeToolInput(
                    id="github-check-read",
                    tool_id="github-actions",
                    operation_id="view-run",
                    actor_id="qa",
                    swarm_id=SWARM,
                    work_id=WORK,
                    inputs={"run": "9001"},
                    read_only_sync=True,
                )
            ),
        ]
        try:
            lifecycle.ws.invoke_tool(
                InvokeToolInput(
                    id="github-issue-write",
                    tool_id="github-issues",
                    operation_id="create",
                    actor_id="po",
                    swarm_id=SWARM,
                    work_id=WORK,
                    inputs={
                        "project": fixture["project"],
                        "type": "Task",
                        "title": "Not authorized",
                        "description": "Read-only profile must reject this write.",
                    },
                )
            )
        except PermissionError as error:
            denied_write = str(error)
        else:
            raise AssertionError("read-only Core role unexpectedly prepared a GitHub write")

        for kind, uri in zip(
            ("github-issue", "github-pull-request", "github-check-run"),
            snapshot["evidence_references"],
            strict=True,
        ):
            lifecycle.ws.add_artifact(
                AddArtifactInput(
                    swarm_id=SWARM,
                    work_id=WORK,
                    actor_id="po",
                    kind=kind,
                    uri=uri,
                )
            )
        lifecycle.ws.add_evidence(
            AddEvidenceInput(
                swarm_id=SWARM,
                work_id=WORK,
                actor_id="build",
                type="github-delivery",
                result="success",
                artifact_refs=snapshot["evidence_references"],
                environment="offline-fixture",
                exit_code=0,
            )
        )
        lifecycle.to_intent()
        lifecycle.to_inception()
        lifecycle.to_construction()
        lifecycle.to_operations()
        lifecycle.to_completed()
        validation = lifecycle.ws.validate()
        summary = {
            "final_state": lifecycle.state(),
            "validate": "ok" if validation.ok else "failed",
            "profile_mode": "read-only",
            "adapters": list(adapters),
            "prepared_operations": [f"{run.tool_id}/{run.operation_id}" for run in prepared],
            "delivery_allowed": snapshot["allowed"],
            "evidence_references": snapshot["evidence_references"],
            "idempotent_ingest": created and not duplicate_created and len(observations) == 1,
            "write_policy_denied": not authorize_operation("issue-create")["allowed"],
            "core_write_denied": "issue.write" in denied_write,
        }
        print(json.dumps(summary, sort_keys=True))
        if summary["validate"] == "ok":
            shutil.rmtree(runtime)
        else:
            summary["workspace"] = str(project)
        return summary
    except Exception:
        print(json.dumps({"workspace": str(project), "status": "failed"}, sort_keys=True))
        raise


if __name__ == "__main__":
    main()
