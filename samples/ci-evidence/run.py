"""Credential-free, multi-provider CI evidence sample."""

import json
import shutil
import tempfile
from pathlib import Path

from agora.model import AddArtifactInput

from agora_ai_sdlc.ci_evidence import (
    core_evidence_input,
    evaluate_bundle,
    ingest_evidence,
    normalize_evidence,
)
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle

HERE = Path(__file__).parent
REPOSITORY = "https://github.com/example/product"
COMMIT = "a" * 40


def _load_facts() -> list[dict]:
    facts = []
    for name in ("github-actions", "gitlab-ci", "jenkins"):
        facts.extend(json.loads((HERE / f"{name}.json").read_text(encoding="utf-8")))
    return facts


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-ci-evidence-"))
    project = runtime / "project"
    lifecycle = Lifecycle(project, runtime / "home")
    try:
        observations: tuple[dict, ...] = ()
        duplicate_created = True
        for payload in _load_facts():
            expected_environment = "staging" if payload["category"] in {"deployment", "smoke-test"} else "ci"
            fact = normalize_evidence(
                payload,
                expected_repository=REPOSITORY,
                expected_commit=COMMIT,
                expected_environment=expected_environment,
            )
            observations, _ = ingest_evidence(observations, fact)
            observations, duplicate_created = ingest_evidence(observations, fact)

        lifecycle.to_intent()
        lifecycle.to_inception()
        lifecycle.to_construction()
        for index, reference in enumerate(
            dict.fromkeys(ref for fact in observations for ref in fact["evidence_refs"]),
            start=1,
        ):
            lifecycle.ws.add_artifact(
                AddArtifactInput(
                    swarm_id=SWARM,
                    work_id=WORK,
                    actor_id="po",
                    kind=f"ci-evidence-{index}",
                    uri=reference,
                )
            )

        test_suite = evaluate_bundle(
            "test-suite",
            observations,
            expected_repository=REPOSITORY,
            expected_commit=COMMIT,
            expected_environment="ci",
        )
        lifecycle.ws.add_evidence(
            core_evidence_input(
                test_suite,
                swarm_id=SWARM,
                work_id=WORK,
                actor_id="build",
            )
        )
        lifecycle.stage("build", "built")
        lifecycle.stage("qa", "verified")
        lifecycle.artifact("build", "implementation-plan")
        lifecycle.artifact("build", "test-strategy")
        lifecycle.approve("qa", "quality-reviewer")
        assert lifecycle.move("qa", "operations") == "operations"

        security = evaluate_bundle(
            "security-scan",
            observations,
            expected_repository=REPOSITORY,
            expected_commit=COMMIT,
            expected_environment="ci",
        )
        deployment = evaluate_bundle(
            "deployment",
            observations,
            expected_repository=REPOSITORY,
            expected_commit=COMMIT,
            expected_environment="staging",
        )
        for bundle in (security, deployment):
            lifecycle.ws.add_evidence(
                core_evidence_input(
                    bundle,
                    swarm_id=SWARM,
                    work_id=WORK,
                    actor_id="ops",
                )
            )
        for kind in ("deployment-plan", "rollback-procedure", "operational-readiness"):
            lifecycle.artifact("ops", kind)
        lifecycle.stage("ops", "deployed")
        lifecycle.stage("po", "accepted")
        lifecycle.approve("po", "product-owner")
        assert lifecycle.move("po", "completed") == "completed"

        validation = lifecycle.ws.validate()
        summary = {
            "final_state": lifecycle.state(),
            "validate": "ok" if validation.ok else "failed",
            "providers": sorted({fact["provider"] for fact in observations}),
            "categories": sorted({fact["category"] for fact in observations}),
            "bundles": {bundle["evidence_type"]: bundle["allowed"] for bundle in (test_suite, security, deployment)},
            "observations": len(observations),
            "idempotent_ingest": not duplicate_created,
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
