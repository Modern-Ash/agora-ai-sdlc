"""Credential-free GitLab delivery profile sample."""

import json
import shutil
import tempfile
from pathlib import Path

from agora.model import AddArtifactInput, AddEvidenceInput, InvokeToolInput

from agora_ai_sdlc.follow_on_delivery import (
    authorize_operation,
    install_read_only,
    normalize_gitlab_delivery,
    reconcile_observation,
)
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle

HERE = Path(__file__).parent


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-gitlab-delivery-"))
    project = runtime / "project"
    lifecycle = Lifecycle(project, runtime / "home")
    try:
        adapters = install_read_only("gitlab", lifecycle.ws, project)
        fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
        snapshot = normalize_gitlab_delivery(**fixture)
        observations, created = reconcile_observation((), snapshot)
        observations, duplicate_created = reconcile_observation(observations, snapshot)
        prepared = [
            lifecycle.ws.invoke_tool(
                InvokeToolInput(
                    id="gitlab-issue-read",
                    tool_id="gitlab-issues",
                    operation_id="view",
                    actor_id="po",
                    swarm_id=SWARM,
                    work_id=WORK,
                    inputs={"issue": "30"},
                    read_only_sync=True,
                )
            ),
            lifecycle.ws.invoke_tool(
                InvokeToolInput(
                    id="gitlab-mr-read",
                    tool_id="gitlab-merge-requests",
                    operation_id="view",
                    actor_id="build",
                    swarm_id=SWARM,
                    work_id=WORK,
                    inputs={"review": "65"},
                    read_only_sync=True,
                )
            ),
            lifecycle.ws.invoke_tool(
                InvokeToolInput(
                    id="gitlab-pipeline-read",
                    tool_id="gitlab-ci",
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
                    id="gitlab-issue-write",
                    tool_id="gitlab-issues",
                    operation_id="comment",
                    actor_id="po",
                    swarm_id=SWARM,
                    work_id=WORK,
                    inputs={"issue": "30", "body": "Not authorized"},
                )
            )
        except PermissionError as error:
            denied_write = str(error)
        else:
            raise AssertionError("read-only Core role unexpectedly prepared a GitLab write")

        for kind, uri in zip(
            ("gitlab-issue", "gitlab-merge-request", "gitlab-pipeline"),
            snapshot["evidence_references"],
            strict=True,
        ):
            lifecycle.ws.add_artifact(AddArtifactInput(swarm_id=SWARM, work_id=WORK, actor_id="po", kind=kind, uri=uri))
        lifecycle.ws.add_evidence(
            AddEvidenceInput(
                swarm_id=SWARM,
                work_id=WORK,
                actor_id="build",
                type="gitlab-delivery",
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
            "provider": "gitlab",
            "profile_mode": "read-only",
            "adapters": list(adapters),
            "prepared_operations": [f"{run.tool_id}/{run.operation_id}" for run in prepared],
            "delivery_allowed": snapshot["allowed"],
            "idempotent_reconciliation": created and not duplicate_created and len(observations) == 1,
            "write_policy_denied": not authorize_operation("gitlab", "issue-comment")["allowed"],
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
