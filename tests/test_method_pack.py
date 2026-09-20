import json
import shutil
import subprocess
import sys
from itertools import pairwise
from pathlib import Path

import pytest

PACK = Path(__file__).parent.parent / "registry" / "methods" / "ai-sdlc"
STATES = ["readiness", "intent", "inception", "construction", "operations", "completed"]
FORWARD = list(pairwise(STATES))
REWORK = [("inception", "intent"), ("construction", "inception"), ("operations", "construction")]


def front(path: Path) -> dict:
    lines = path.read_text().split("\n")
    end = lines.index("---", 1)
    out = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        try:
            out[key.strip()] = json.loads(value.strip())
        except ValueError:
            out[key.strip()] = value.strip()
    return out


def transitions():
    return [front(p) for p in sorted((PACK / "transitions").glob("*.md"))]


def edges():
    return {(t["from"], t["to"]) for t in transitions()}


def test_manifest_states_and_terminal():
    method = front(PACK / "METHOD.md")
    assert method["work-states"] == STATES
    assert method["terminal-state"] == "completed"


def test_every_state_reachable_from_initial():
    seen, todo = {STATES[0]}, [STATES[0]]
    while todo:
        cur = todo.pop()
        for a, b in edges():
            if a == cur and b not in seen:
                seen.add(b)
                todo.append(b)
    assert seen == set(STATES)


def test_completed_is_terminal_and_edges_exact():
    assert not [e for e in edges() if e[0] == "completed"]
    assert edges() == set(FORWARD) | set(REWORK)


@pytest.mark.parametrize("edge", [("intent", "readiness"), ("readiness", "completed"), ("completed", "operations")])
def test_undeclared_transitions_absent(edge):
    assert edge not in edges()


def test_forward_transitions_reference_existing_gates_and_roles():
    gates = {front(p)["id"] for p in (PACK / "gates").glob("*.md")}
    roles = {front(p)["id"] for p in (PACK / "roles").glob("*.md")}
    assert set(front(PACK / "METHOD.md")["required-roles"]) <= roles
    for t in transitions():
        assert set(t["roles"]) <= roles
        if (t["from"], t["to"]) in FORWARD:
            assert t["gate"] in gates
        else:
            assert "gate" not in t


def test_no_vendor_assumptions():
    banned = ("aws", "bedrock", "openai", "anthropic", "kiro", "amazon", "gpt", "claude", "gemini")
    for path in PACK.rglob("*.md"):
        text = path.read_text().lower()
        assert not [w for w in banned if w in text], path


def test_core_installs_and_validates_pack(tmp_path):
    def agora(*args):
        return subprocess.run(
            [sys.executable, "-m", "agora", *args], cwd=tmp_path, capture_output=True, text=True, check=False
        )

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert agora("init", "--path", ".").returncode == 0
    assert agora("method", "install", "--source", str(PACK), "--scope", "project").returncode == 0
    assert agora("validate").returncode == 0


def test_core_rejects_broken_pack(tmp_path):
    bad = tmp_path / "pack"
    shutil.copytree(PACK, bad)
    (bad / "transitions" / "01-readiness-intent.md").write_text(
        '---\nschema: "agora/transition/v1"\nfrom: "readiness"\nto: "nowhere"\nroles: ["product-owner"]\n---\n'
    )
    project = tmp_path / "proj"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    subprocess.run([sys.executable, "-m", "agora", "init", "--path", "."], cwd=project, capture_output=True, check=True)
    result = subprocess.run(
        [sys.executable, "-m", "agora", "method", "install", "--source", str(bad), "--scope", "project"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
