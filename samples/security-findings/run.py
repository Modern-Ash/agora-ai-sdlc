"""Credential-free security finding normalization and decision sample."""

import json
import shutil
import tempfile
from pathlib import Path

from agora.model import AddActorInput, AddArtifactInput

from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle
from agora_ai_sdlc.security_findings import (
    decide_finding,
    evaluate_findings,
    normalize_finding,
    security_evidence_input,
    to_core_decision_input,
    to_core_finding_input,
)

HERE = Path(__file__).parent
COMMIT = "a" * 40
SCAN_REF = "https://security.example.com/reports/change-42"


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-security-findings-"))
    project = runtime / "project"
    lifecycle = Lifecycle(project, runtime / "home")
    try:
        lifecycle.ws.add_actor(
            AddActorInput(
                id="security",
                name="Security Reviewer",
                kind="human",
                capabilities=["security-review"],
                scope="project",
            )
        )
        lifecycle.ws.add_actor(
            AddActorInput(
                id="governance",
                name="Governance Owner",
                kind="human",
                capabilities=["governance"],
                scope="project",
            )
        )
        lifecycle.to_intent()
        lifecycle.to_inception()
        lifecycle.to_construction()
        lifecycle.to_operations()

        entries = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
        open_findings = [normalize_finding(entry["finding"]) for entry in entries]
        for finding in open_findings:
            lifecycle.ws.add_review_finding(to_core_finding_input(finding, swarm_id=SWARM, work_id=WORK))
        blocked = evaluate_findings("standard", open_findings, scan_refs=[SCAN_REF])

        findings = []
        for entry, finding in zip(entries, open_findings, strict=True):
            if "decision" in entry:
                finding = decide_finding(finding, entry["decision"])
                lifecycle.ws.decide_review_finding(to_core_decision_input(finding))
            findings.append(finding)
        assessment = evaluate_findings("standard", findings, scan_refs=[SCAN_REF])

        for index, reference in enumerate(assessment["references"], start=1):
            lifecycle.ws.add_artifact(
                AddArtifactInput(
                    swarm_id=SWARM,
                    work_id=WORK,
                    actor_id="qa",
                    kind=f"security-reference-{index}",
                    uri=reference,
                )
            )
        lifecycle.ws.add_evidence(
            security_evidence_input(
                assessment,
                swarm_id=SWARM,
                work_id=WORK,
                actor_id="qa",
                tested_commit=COMMIT,
                environment="ci",
            )
        )
        lifecycle.prepare_completion(skip="security-scan")
        assert lifecycle.move("po", "completed") == "completed"
        validation = lifecycle.ws.validate()
        summary = {
            "final_state": lifecycle.state(),
            "validate": "ok" if validation.ok else "failed",
            "categories": sorted({finding["category"] for finding in findings}),
            "blocked_before_decisions": not blocked["allowed"],
            "allowed_after_decisions": assessment["allowed"],
            "decisions": sorted(finding["status"] for finding in findings if finding["status"] != "open"),
            "open_below_threshold": sorted(finding["id"] for finding in findings if finding["status"] == "open"),
            "core_statuses": sorted(item.status for item in lifecycle.ws.list_review_findings(SWARM, WORK)),
        }
        print(json.dumps(summary, sort_keys=True))
        if validation.ok:
            shutil.rmtree(runtime)
        else:
            summary["workspace"] = str(project)
        return summary
    except Exception:
        print(json.dumps({"workspace": str(project), "status": "failed"}, sort_keys=True))
        raise


if __name__ == "__main__":
    main()
