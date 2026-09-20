"""Offline existing-codebase pilot with provider replacement and independent review."""

import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from agora.model import AddArtifactInput, SetActorRuntimeInput, StartSessionInput

from agora_ai_sdlc.ci_evidence import core_evidence_input, evaluate_bundle, normalize_evidence
from agora_ai_sdlc.independent_review import ArtifactRevision, Review, evaluate_review
from agora_ai_sdlc.provenance import parse
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle

HERE = Path(__file__).parent
REPOSITORY = "https://github.com/example/existing-catalog"


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _git(project: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _commit(project: Path, message: str) -> str:
    _git(project, "add", "catalog.py", "test_catalog.py", "CHANGE_REQUEST.md")
    _git(project, "-c", "user.name=Agora Pilot", "-c", "user.email=pilot@example.invalid", "commit", "-qm", message)
    return _git(project, "rev-parse", "HEAD")


def _tests(project: Path) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"Ran (\d+) tests?", result.stderr)
    return {"status": "success" if result.returncode == 0 else "failure", "tests": int(match[1]) if match else 0}


def _session(lifecycle: Lifecycle, session_id: str, actor: str, operation: str, runtime: dict) -> tuple[object, dict]:
    lifecycle.ws.set_actor_runtime(SetActorRuntimeInput(actor_id=actor, **runtime))
    capture = lifecycle.root / "pilot" / f"{session_id}.json"
    runner = shlex.join(
        [
            sys.executable,
            str(HERE / "fake_runner.py"),
            "--adapter",
            runtime["integration"],
            "--operation",
            operation,
            "--capture",
            str(capture),
        ]
    )
    session = lifecycle.ws.start_session(
        StartSessionInput(
            id=session_id,
            actor_id=actor,
            swarm_id=SWARM,
            work_id=WORK,
            runner=runner,
            launch=True,
        )
    )
    return session, json.loads(capture.read_text(encoding="utf-8"))


def _observed(session, subject: ArtifactRevision):
    value = lambda item: {"value": item, "source": "observed"}
    return parse(
        {
            "schema": "agora-ai-sdlc/provenance/v1",
            "actor": session.executor or session.actor,
            "runtime": value(session.integration),
            "runtime_version": value("fake-1.0"),
            "provider": value(session.provider),
            "model": value(session.model),
            "selection_reason": value("existing-codebase pilot route"),
            "fallback": {"source": "observed", "used": False},
            "subject": {
                "kind": subject.kind,
                "id": subject.id,
                "revision": subject.revision,
                "digest": subject.digest,
            },
        }
    )


def _review(producer_session, reviewer_session, verdict: str, revision: int, project: Path) -> tuple[dict, dict]:
    subject = ArtifactRevision(
        "implementation",
        "catalog-pricing",
        revision,
        _file_digest(project / "catalog.py"),
        ("distinct-actor", "distinct-provider"),
    )
    producer = _observed(producer_session, subject)
    reviewer = _observed(reviewer_session, subject)
    decision = evaluate_review(
        produced=subject,
        producer=producer,
        review=Review(
            actor=reviewer.actor,
            actor_kind="ai-agent",
            role="quality-reviewer",
            subject=subject,
            verdict=verdict,
            provenance=reviewer,
        ),
    )
    visible = {
        "revision": revision,
        "verdict": verdict,
        "allowed": decision["allowed"],
        "blockers": [item["code"] for item in decision["blockers"]],
        "producer": {
            "actor": producer.actor,
            "runtime": producer.runtime.value,
            "provider": producer.provider.value,
            "model": producer.model.value,
        },
        "reviewer": {
            "actor": reviewer.actor,
            "runtime": reviewer.runtime.value,
            "provider": reviewer.provider.value,
            "model": reviewer.model.value,
        },
    }
    return decision, visible


def _ci_evidence(lifecycle: Lifecycle, commit: str) -> dict:
    facts = []
    for index, category in enumerate(("build", "unit", "integration", "quality"), start=1):
        reference = f"https://ci.example.com/existing-catalog/runs/38/jobs/{index}"
        lifecycle.ws.add_artifact(AddArtifactInput(SWARM, WORK, "build", f"ci-{category}", reference))
        facts.append(
            normalize_evidence(
                {
                    "schema": "agora-ai-sdlc/ci-evidence/v1",
                    "provider": "offline-pilot-ci",
                    "repository": REPOSITORY,
                    "commit": commit,
                    "environment": "ci",
                    "run_id": f"pilot-38-{category}",
                    "category": category,
                    "status": "success",
                    "evidence_refs": [reference],
                },
                expected_repository=REPOSITORY,
                expected_commit=commit,
                expected_environment="ci",
            )
        )
    bundle = evaluate_bundle(
        "test-suite", facts, expected_repository=REPOSITORY, expected_commit=commit, expected_environment="ci"
    )
    lifecycle.ws.add_evidence(core_evidence_input(bundle, swarm_id=SWARM, work_id=WORK, actor_id="build"))
    return bundle


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-existing-codebase-pilot-"))
    project = runtime / "project"
    lifecycle = Lifecycle(project, runtime / "home")
    try:
        shutil.copyfile(HERE / "fixture" / "catalog.py", project / "catalog.py")
        shutil.copyfile(HERE / "fixture" / "test_catalog.py", project / "test_catalog.py")
        shutil.copyfile(HERE / "CHANGE_REQUEST.md", project / "CHANGE_REQUEST.md")
        baseline_commit = _commit(project, "chore: capture maintained baseline")
        baseline = _tests(project)
        lifecycle.to_intent()
        lifecycle.to_inception()
        lifecycle.to_construction()

        method_pack = project / ".agora" / "methods" / "ai-sdlc"
        method_before = _tree_digest(method_pack)
        first_runtime = {"integration": "codex", "provider": "provider-alpha", "model": "producer-a"}
        producer_one, _ = _session(lifecycle, "implementation-a", "build", "implement", first_runtime)
        first_commit = _commit(project, "feat: add volume pricing")
        first_result = _tests(project)
        review_runtime = {"integration": "claude", "provider": "provider-review", "model": "reviewer"}
        reviewer_one, first_review_output = _session(lifecycle, "review-a", "arch", "review", review_runtime)
        first_review, first_visible = _review(producer_one, reviewer_one, first_review_output["verdict"], 1, project)
        assert not first_review["allowed"] and first_result["status"] == "success"

        lifecycle.stage("build", "built")
        lifecycle.artifact("build", "implementation-plan")
        lifecycle.artifact("build", "test-strategy")
        blocked_gate = None
        try:
            lifecycle.move("qa", "operations")
        except ValueError as error:
            blocked_gate = str(error).split(":")[0]
        else:
            raise AssertionError("rejected implementation must not reach operations")

        replacement_runtime = {"integration": "generic", "provider": "provider-beta", "model": "producer-b"}
        producer_two, _ = _session(lifecycle, "implementation-b", "build", "correct", replacement_runtime)
        final_commit = _commit(project, "fix: validate quote quantities")
        final_result = _tests(project)
        reviewer_two, final_review_output = _session(lifecycle, "review-b", "arch", "review", review_runtime)
        final_review, final_visible = _review(producer_two, reviewer_two, final_review_output["verdict"], 2, project)
        method_after = _tree_digest(method_pack)
        assert final_review["allowed"] and final_result["status"] == "success"
        assert method_before == method_after

        bundle = _ci_evidence(lifecycle, final_commit)
        lifecycle.stage("qa", "verified")
        lifecycle.approve("qa", "quality-reviewer")
        assert lifecycle.move("qa", "operations") == "operations"
        lifecycle.to_completed()

        metrics = {
            "measured": {
                "baseline_tests": baseline["tests"],
                "baseline_passing": baseline["status"] == "success",
                "first_revision_tests": first_result["tests"],
                "result_tests": final_result["tests"],
                "result_passing": final_result["status"] == "success",
                "review_rounds": 2,
                "gate_rejections": 1,
            },
            "expectations_not_measured": [
                "production defect rate improves",
                "live-provider outputs remain semantically equivalent",
                "delivery lead time decreases",
            ],
        }
        (project / "pilot" / "provenance.json").write_text(
            json.dumps([first_visible, final_visible], indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (project / "pilot" / "metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        validation = lifecycle.ws.validate()
        summary = {
            "sample": "existing-codebase-pilot",
            "final_state": lifecycle.state(),
            "validate": "ok" if validation.ok else "failed",
            "commits": {"baseline": baseline_commit, "rejected": first_commit, "accepted": final_commit},
            "provider_replacement": {
                "before": first_runtime["provider"],
                "after": replacement_runtime["provider"],
                "method_pack_unchanged": method_before == method_after,
            },
            "reviews": [first_visible, final_visible],
            "blocked_gate": blocked_gate,
            "ci": {"allowed": bundle["allowed"], "commit": bundle["commit"], "categories": list(bundle["categories"])},
            "metrics": metrics,
        }
        print(json.dumps(summary, sort_keys=True))
        if summary["final_state"] == "completed" and summary["validate"] == "ok":
            shutil.rmtree(runtime)
        else:
            summary["workspace"] = str(project)
        return summary
    except Exception:
        print(json.dumps({"status": "failed", "workspace": str(project)}, sort_keys=True))
        raise


if __name__ == "__main__":
    main()
