"""Credential-free operational evidence and control-band sample."""

import copy
import json
import shutil
import tempfile
from pathlib import Path

from agora.model import AddArtifactInput

from agora_ai_sdlc.operational_evidence import (
    control_band_inputs,
    core_evidence_input,
    evaluate_readiness,
    normalize_metric,
    normalize_release_observation,
)
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle

HERE = Path(__file__).parent
NOW = "2026-09-20T15:02:00Z"
RELEASE = "product-2026.09.20"
REVISION = "a" * 40
ENVIRONMENT = "production"


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-operational-evidence-"))
    project = runtime / "project"
    lifecycle = Lifecycle(project, runtime / "home")
    try:
        raw_metrics = json.loads((HERE / "metrics.json").read_text(encoding="utf-8"))
        metrics = [
            normalize_metric(
                item["provider"],
                item["payload"],
                expected_environment=ENVIRONMENT,
                observed_at=NOW,
            )
            for item in raw_metrics
        ]
        releases = [
            normalize_release_observation(
                item,
                expected_release=RELEASE,
                expected_revision=REVISION,
                expected_environment=ENVIRONMENT,
                observed_at=NOW,
            )
            for item in json.loads((HERE / "releases.json").read_text(encoding="utf-8"))
        ]
        readiness = evaluate_readiness(
            metrics,
            releases,
            expected_release=RELEASE,
            expected_revision=REVISION,
            expected_environment=ENVIRONMENT,
        )

        severe_payload = copy.deepcopy(raw_metrics[0]["payload"])
        severe_payload["Average"] = 2.0
        severe = normalize_metric(
            "cloudwatch",
            severe_payload,
            expected_environment=ENVIRONMENT,
            observed_at=NOW,
        )
        band_input, evaluation_input = control_band_inputs(severe, "sample-severe-signal")
        lifecycle.ws.add_control_band(band_input)
        finding = lifecycle.ws.evaluate_control_band(evaluation_input)

        lifecycle.to_intent()
        lifecycle.to_inception()
        lifecycle.to_construction()
        lifecycle.to_operations()
        for index, reference in enumerate(readiness["evidence_refs"], start=1):
            lifecycle.ws.add_artifact(
                AddArtifactInput(
                    swarm_id=SWARM,
                    work_id=WORK,
                    actor_id="ops",
                    kind=f"operational-evidence-{index}",
                    uri=reference,
                )
            )
        lifecycle.ws.add_evidence(core_evidence_input(readiness, swarm_id=SWARM, work_id=WORK, actor_id="ops"))
        lifecycle.prepare_completion(skip="deployment")
        assert lifecycle.move("po", "completed") == "completed"
        validation = lifecycle.ws.validate()
        intents = lifecycle.ws.list_intents()
        summary = {
            "final_state": lifecycle.state(),
            "validate": "ok" if validation.ok else "failed",
            "providers": sorted(metric["provider"] for metric in metrics),
            "equivalent_metrics": len({(m["name"], m["value"], m["unit"], m["window"]) for m in metrics}) == 1,
            "readiness_allowed": readiness["allowed"],
            "control_band_level": finding.level,
            "governed_intent": finding.intent_id in {intent.id for intent in intents},
            "production_mutations": 0,
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
