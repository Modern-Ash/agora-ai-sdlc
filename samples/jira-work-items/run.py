"""Credential-free Jira work-management profile sample."""

import json
import shutil
import tempfile
from pathlib import Path

from agora.model import AddArtifactInput, AddEvidenceInput, InvokeToolInput

from agora_ai_sdlc.follow_on_delivery import (
    authorize_operation,
    install_read_only,
    normalize_work_item,
    reconcile_observation,
)
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle

HERE = Path(__file__).parent


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-jira-work-items-"))
    project = runtime / "project"
    lifecycle = Lifecycle(project, runtime / "home")
    try:
        adapters = install_read_only("jira", lifecycle.ws, project)
        fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
        snapshot = normalize_work_item("jira", **fixture)
        observations, created = reconcile_observation((), snapshot)
        observations, duplicate_created = reconcile_observation(observations, snapshot)
        prepared = lifecycle.ws.invoke_tool(
            InvokeToolInput(
                id="jira-work-item-read",
                tool_id="jira",
                operation_id="view",
                actor_id="po",
                swarm_id=SWARM,
                work_id=WORK,
                inputs={"issue": "AGORA-30"},
                read_only_sync=True,
            )
        )
        try:
            lifecycle.ws.invoke_tool(
                InvokeToolInput(
                    id="jira-work-item-transition",
                    tool_id="jira",
                    operation_id="transition",
                    actor_id="po",
                    swarm_id=SWARM,
                    work_id=WORK,
                    inputs={"issue": "AGORA-30", "state": "Done"},
                )
            )
        except PermissionError as error:
            denied_write = str(error)
        else:
            raise AssertionError("read-only Core role unexpectedly prepared a Jira transition")

        evidence_url = snapshot["source"]["url"]
        lifecycle.ws.add_artifact(
            AddArtifactInput(
                swarm_id=SWARM,
                work_id=WORK,
                actor_id="po",
                kind="jira-work-item",
                uri=evidence_url,
            )
        )
        lifecycle.ws.add_evidence(
            AddEvidenceInput(
                swarm_id=SWARM,
                work_id=WORK,
                actor_id="po",
                type="jira-work-management",
                result="success",
                artifact_refs=[evidence_url],
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
            "provider": "jira",
            "profile_mode": "read-only",
            "adapters": list(adapters),
            "prepared_operations": [f"{prepared.tool_id}/{prepared.operation_id}"],
            "normalized_outcome": snapshot["outcome"],
            "agora_lifecycle_authority": lifecycle.state() == "completed" and snapshot["outcome"]["state"] == "open",
            "idempotent_reconciliation": created and not duplicate_created and len(observations) == 1,
            "write_policy_denied": not authorize_operation("jira", "work-item-transition")["allowed"],
            "core_write_denied": "issue.transition" in denied_write,
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
