import json
from pathlib import Path

import pytest
from test_observation import snapshot
from test_start_flow import FakeWorkspace, runtime

from agora_ai_sdlc.cli import main
from agora_ai_sdlc.observation import agent_summary
from agora_ai_sdlc.start_preflight import StartPreparationResult


def test_cli_json_does_not_include_ui_even_if_both_streams_are_captured(tmp_path, monkeypatch, capsys):
    s = snapshot(tmp_path)
    monkeypatch.setattr("agora_ai_sdlc.observation_cli.collect", lambda *a, **k: s)
    responses = []
    for detail in ("normal", "detailed", "diagnostic"):
        for lang in ("en", "es"):
            assert (
                main(
                    [
                        "observe",
                        "--swarm",
                        "delivery",
                        "--work",
                        "issue-8",
                        "--json",
                        "--detail",
                        detail,
                        "--lang",
                        lang,
                    ]
                )
                == 0
            )
            out = capsys.readouterr()
            assert out.err == ""
            responses.append(out.out)
    assert len(set(responses)) == 1
    assert json.loads(responses[0]) == agent_summary(s)


def test_json_and_separate_human_file(tmp_path, monkeypatch, capsys):
    s = snapshot(tmp_path)
    monkeypatch.setattr("agora_ai_sdlc.observation_cli.collect", lambda *a, **k: s)
    file = tmp_path / "human.log"
    assert (
        main(
            [
                "observe",
                "--swarm",
                "delivery",
                "--work",
                "issue-8",
                "--json",
                "--detail",
                "diagnostic",
                "--lang",
                "es",
                "--ui-file",
                str(file),
            ]
        )
        == 0
    )
    out = capsys.readouterr()
    assert out.err == ""
    assert json.loads(out.out) == agent_summary(s)
    assert "Observación" in file.read_text()
    assert "Actividad reciente" in file.read_text()
    assert "Actividad" not in out.out


def test_watch_never_streams_to_agent_json(monkeypatch, capsys):
    monkeypatch.setattr("agora_ai_sdlc.observation_cli.collect", lambda *a, **k: pytest.fail("must not read"))
    assert main(["observe", "--swarm", "delivery", "--work", "issue-8", "--json", "--watch"]) == 2
    out = capsys.readouterr()
    assert out.err == ""
    assert json.loads(out.out)["code"] == "observation.watch-is-human-only"


def test_start_progress_never_changes_result_or_handoff(tmp_path):
    from agora_ai_sdlc.start_flow import prepare_start

    workspace = FakeWorkspace(tmp_path)
    options = {
        "issue": 11,
        "project": "Modern-Ash/agorix",
        "workspace_factory": lambda cwd: workspace,
        "runtime_discovery": lambda root: (runtime(),),
    }
    no_isolation = lambda root, issue: (root.resolve(), None)
    no_preflight = lambda root, runtime, **kwargs: StartPreparationResult(root.resolve(), ())
    baseline = prepare_start(
        tmp_path,
        **options,
        isolation=no_isolation,
        preflight=no_preflight,
        launch_executor=False,
    )
    content = Path(baseline.handoff_path).read_bytes()
    events = []
    observed = prepare_start(
        tmp_path,
        **options,
        isolation=no_isolation,
        preflight=no_preflight,
        launch_executor=False,
        progress=events.append,
    )
    assert observed.snapshot() == baseline.snapshot()
    assert Path(observed.handoff_path).read_bytes() == content
    assert "start.issue-reused" in events
    assert events[-1] == "start.prepared"
    assert "start.failed" not in events


def test_start_json_uses_explicit_file_for_progress(tmp_path, monkeypatch, capsys):
    from agora_ai_sdlc import start_flow

    original = start_flow.prepare_start
    workspace = FakeWorkspace(tmp_path)

    def prepared(root, **options):
        return original(
            root,
            **options,
            workspace_factory=lambda cwd: workspace,
            runtime_discovery=lambda r: (runtime(),),
            isolation=lambda candidate, issue: (candidate.resolve(), None),
            preflight=lambda candidate, runtime, **kwargs: StartPreparationResult(candidate.resolve(), ()),
            launch_executor=False,
        )

    monkeypatch.setattr(start_flow, "prepare_start", prepared)
    file = tmp_path / "start.log"
    assert (
        main(
            [
                "start",
                "--issue",
                "11",
                "--project",
                "Modern-Ash/agorix",
                "--root",
                str(tmp_path),
                "--json",
                "--lang",
                "es",
                "--ui-file",
                str(file),
            ]
        )
        == 0
    )
    out = capsys.readouterr()
    assert out.err == ""
    assert json.loads(out.out)["intent_id"] == "issue-11"
    human = file.read_text()
    assert "Start no lanzó el executor" in human
    assert "Leyendo el issue" in human
    assert "100% 12/12" in human
    assert "Work gobernado y rama del issue resueltos" in human
    assert "[" not in out.out.split("intent_id")[0]  # no progress prefix


def test_skill_json_default_is_metadata_only(capsys):
    assert main(["skill", "--phase", "review", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["token_count"] is None
    assert [r["path"] for r in result["resources"]] == ["SKILL.md", "references/review.md"]
    assert all("content" not in r for r in result["resources"])
    assert main(["skill", "--phase", "review", "--json", "--content"]) == 0
    with_content = json.loads(capsys.readouterr().out)
    assert "content" in with_content["resources"][0]


def test_skill_sync_changes_only_skill_resources(tmp_path, monkeypatch, capsys):
    from test_installer import base_config

    from agora_ai_sdlc.installer import apply

    root, home = tmp_path / "project", tmp_path / "home"
    monkeypatch.setenv("AGORA_HOME", str(home))
    apply(base_config(), root, home)
    guide = root / ".agora" / "skills" / "agora-ai-sdlc-guided"
    (guide / "SKILL.md").write_text("old skill")
    (guide / "custom.md").write_text("user addition")
    before = {p: p.read_bytes() for p in (root / ".agora").rglob("*") if p.is_file() and guide not in p.parents}
    assert main(["skill", "--install", "--root", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["resources"] == 7
    assert (guide / "custom.md").read_text() == "user addition"
    after = {p: p.read_bytes() for p in (root / ".agora").rglob("*") if p.is_file() and guide not in p.parents}
    assert before == after
