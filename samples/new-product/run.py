"""Credential-free AI-SDLC scenario: a new product taken from readiness to completed.

Exercises a blocked gate, clarification, artifacts, criteria, approvals, evidence, one rework loop
(construction -> inception) and completion in a throwaway Git repository, then runs `agora validate`.
Prints a machine-checkable JSON summary. Run with: agora-ai-sdlc run-sample new-product
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from agora_ai_sdlc.scenario import Lifecycle


def transitions(project: Path) -> list[dict[str, str]]:
    found = []
    for line in (project / ".agora" / "activity.md").read_text().splitlines():
        if "| work.transitioned |" in line:
            match = re.search(r"from=(\S+) to=(\S+) actor=(\S+)", line)
            found.append({"from": match[1], "to": match[2], "actor": match[3]})
    return found


def actions(project: Path) -> list[str]:
    return [
        line.split("|")[1].strip()
        for line in (project / ".agora" / "activity.md").read_text().splitlines()
        if line.startswith("- ")
    ]


def main() -> dict:
    workdir = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-sample-"))
    project = workdir / "project"
    life = Lifecycle(project, workdir / "home")
    blocked = []

    def expect_block(actor: str, target: str) -> None:
        try:
            life.move(actor, target)
        except ValueError as error:
            blocked.append({"target": target, "reason": str(error).split(":")[0]})
            return
        raise AssertionError(f"gate to {target} should have blocked")

    # readiness: a gate blocks until the assessment exists, is clarified and approved
    expect_block("po", "intent")
    life.to_intent()
    life.to_inception()
    life.to_construction()

    # rework: construction found a design gap, go back to inception with a rework record
    expect_block("arch", "inception")
    life.artifact("arch", "rework-record")
    life.move("arch", "inception")
    life.clarify()
    life.move("arch", "construction")

    life.to_operations()
    life.to_completed()

    validated = subprocess.run(
        [sys.executable, "-m", "agora", "validate"], cwd=project, capture_output=True, text=True, check=False
    )
    summary = {
        "sample": "new-product",
        "final_state": life.state(),
        "transitions": transitions(project),
        "blocked_gates": blocked,
        "rework_paths": [t for t in transitions(project) if (t["from"], t["to"]) == ("construction", "inception")],
        "activity_actions": sorted(set(actions(project))),
        "validate": "ok" if validated.returncode == 0 else "failed",
    }
    if summary["final_state"] == "completed" and summary["validate"] == "ok":
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        summary["workspace"] = str(workdir)  # kept for diagnosis
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
