import json
from copy import deepcopy
from io import StringIO
from types import SimpleNamespace as NS

import pytest

from agora_ai_sdlc.observation import agent_summary, collect
from agora_ai_sdlc.observation_ui import HumanChannel, render, safe_text, watch


def objects():
    work = NS(
        id="issue-8",
        swarm_id="delivery",
        title="Learner journey",
        revision=1,
        state="inception",
        operational_status="active",
        acceptance_criteria={"layout": "Visible code"},
        satisfied_criteria=[],
        approval_roles=[],
        branch="ai-sdlc/issue-8",
        base_branch="main",
    )
    blocker = NS(
        code="approval.missing",
        category="approval",
        references=("product-owner",),
        message="password=SHOULD_NOT_TRAVEL",
    )
    gate = NS(
        id="inception-approved",
        satisfied=False,
        required_approval_roles=("product-owner",),
        required_artifacts=("requirements",),
        required_evidence_types=(),
        blockers=(blocker,),
    )
    transition = NS(
        source="inception", target="construction", gate_id=gate.id, available=False, authorized_roles=("product-owner",)
    )
    life = NS(
        work_id=work.id,
        swarm_id=work.swarm_id,
        method="ai-sdlc",
        current_state=work.state,
        operational_status="active",
        terminal_state="completed",
        transitions=(transition,),
        gates=(gate,),
    )
    session = NS(
        id="session-8",
        swarm_id="delivery",
        work_id="issue-8",
        actor="project:developer",
        executor="project:ai-primary",
        status="prepared",
        integration="generic",
        provider="local",
        model="local-model",
        created_at="2026-09-22T10:00:00Z",
        exit_code=None,
        timeout_seconds=300,
        output_bytes=0,
        execution_profile="bounded",
        context_sha256="a" * 64,
        launch_command=("runner", "--token=SHOULD_NOT_TRAVEL"),
        authorization_signature="SHOULD_NOT_TRAVEL",
        context="SHOULD_NOT_TRAVEL",
        provenance=None,
    )
    event = NS(
        timestamp="2026-09-22T10:00:01Z",
        type="session.prepared",
        actor="project:developer",
        swarm_id="delivery",
        work_id="issue-8",
        session_id="session-8",
        tool_run_id=None,
        summary="private child info and password=SHOULD_NOT_TRAVEL",
    )
    artifact = NS(
        kind="requirements",
        uri="repo://docs/product.md",
        content_sha256="b" * 64,
        produced_by="project:developer",
        timestamp="2026-09-22T10:00:00Z",
    )
    usage = NS(
        records=0, budget_limits={"tokens": 1000}, consumed={}, consumed_measurement={}, remaining={"tokens": 1000}
    )
    workspace = NS(show_work=lambda s, w: work, summarize_usage=lambda s, w: usage)
    read = NS(
        lifecycle=lambda s, w: life,
        list_sessions=lambda: (session,),
        activity=lambda f: (event,),
        artifacts=lambda s, w: (artifact,),
    )
    return NS(
        work=work,
        lifecycle=life,
        gate=gate,
        transition=transition,
        session=session,
        event=event,
        artifact=artifact,
        usage=usage,
        workspace=workspace,
        read=read,
    )


def snapshot(tmp_path, o=None, **kw):
    o = o or objects()
    return collect(
        tmp_path,
        swarm="delivery",
        work="issue-8",
        workspace_factory=lambda cwd: o.workspace,
        read_factory=lambda ws: o.read,
        **kw,
    )


def test_observer_is_read_only_scoped_and_keeps_pending_authority(tmp_path):
    s = snapshot(tmp_path)
    assert s["status"] == "observed"
    assert s["scope"] == {"swarm": "delivery", "work": "issue-8"}
    assert s["work"]["branch"] == "ai-sdlc/issue-8"
    assert s["gates"][0]["satisfied"] is False
    assert s["next_action"] == "resolve-core-obligations"
    assert s["read_only"] is True
    assert not list(tmp_path.iterdir())


def test_verbose_human_views_never_modify_machine_context(tmp_path):
    s = snapshot(tmp_path)
    before = json.dumps(agent_summary(s), sort_keys=True)
    outputs = set()
    for lang in ("en", "es"):
        for detail in ("normal", "detailed", "diagnostic"):
            outputs.add(render(s, detail=detail, lang=lang))
            assert json.dumps(agent_summary(s), sort_keys=True) == before
    assert len(outputs) == 6
    assert "activity" not in agent_summary(s)
    assert "observed_at" not in agent_summary(s)
    assert "SHOULD_NOT_TRAVEL" not in json.dumps(s)
    assert "SHOULD_NOT_TRAVEL" not in "".join(outputs)


def test_unreported_usage_is_not_zero_or_remaining_budget(tmp_path):
    s = snapshot(tmp_path)
    tokens = s["usage"]["dimensions"]["tokens"]
    assert tokens == {"recorded": None, "measurement": "unknown", "limit": 1000, "remaining": None}
    assert s["usage"]["cost_usd"] is None
    assert s["sessions"][0]["basis"] == {"runtime": "unavailable", "provider": "unavailable", "model": "unavailable"}


@pytest.mark.parametrize("basis", ["measured", "provider-reported", "unknown"])
def test_usage_retains_measurement_basis_and_recorded_zero(tmp_path, basis):
    o = objects()
    o.usage.records = 1
    o.usage.consumed = {"tokens": 0}
    o.usage.consumed_measurement = {"tokens": basis}
    s = snapshot(tmp_path, o)
    assert s["usage"]["dimensions"]["tokens"] == {"recorded": 0, "measurement": basis, "limit": 1000, "remaining": 1000}


def test_missing_work_does_not_substitute_first_work(tmp_path):
    o = objects()

    def missing(s, w):
        assert w == "issue-8"
        raise FileNotFoundError("password=SHOULD_NOT_TRAVEL")

    o.workspace.show_work = missing
    s = snapshot(tmp_path, o)
    assert s["status"] == "unavailable"
    assert s["work"] is None
    assert s["warnings"] == ["observation.resource-unavailable"]
    assert "SHOULD_NOT_TRAVEL" not in json.dumps(s)


def test_legacy_work_branch_is_unknown_not_swarm_branch(tmp_path):
    o = objects()
    del o.work.branch
    del o.work.base_branch
    s = snapshot(tmp_path, o)
    assert s["work"]["branch"] is None
    assert s["work"]["branch_basis"] == "unavailable"


def test_changed_during_read_never_suggests_progress(tmp_path):
    o = objects()
    o.transition.available = True
    changed = deepcopy(o.work)
    changed.revision = 2
    records = iter((o.work, changed))
    o.workspace.show_work = lambda s, w: next(records)
    s = snapshot(tmp_path, o)
    assert s["status"] == "partial"
    assert s["next_action"] == "inspect-core-state"
    assert "observation.state-changed-during-read" in s["warnings"]


def test_activity_and_sessions_do_not_leak_other_work(tmp_path):
    o = objects()
    other_event = deepcopy(o.event)
    other_event.work_id = "private-work"
    other_session = deepcopy(o.session)
    other_session.work_id = "private-work"
    o.read.activity = lambda f: (other_event, o.event)
    o.read.list_sessions = lambda: (other_session, o.session)
    s = snapshot(tmp_path, o)
    assert len(s["sessions"]) == len(s["activity"]) == 1
    assert "private-work" not in json.dumps(s)


def test_partial_optional_read_is_explicit_and_has_no_raw_error(tmp_path):
    o = objects()

    def failed(s, w):
        raise ValueError("child@example.test password=SHOULD_NOT_TRAVEL")

    o.workspace.summarize_usage = failed
    s = snapshot(tmp_path, o)
    assert s["status"] == "partial"
    assert s["usage"]["records"] is None
    assert s["warnings"] == ["observation.usage-unavailable"]
    assert "SHOULD_NOT_TRAVEL" not in json.dumps(s)


def test_overflow_cannot_hide_governance_obligation(tmp_path):
    o = objects()
    o.transition.available = True
    o.gate.blockers = o.gate.blockers * 3
    s = snapshot(tmp_path, o, limit=1)
    assert s["gates"][0]["blocker_count"] == 3
    assert s["gates"][0]["truncated"]
    assert s["next_action"] == "inspect-core-state"
    assert "governance" in s["truncated"]
    assert "governance" in render(s, detail="normal")


@pytest.mark.parametrize(
    "dirty",
    [
        "Bearer SECRET_TOKEN_VALUE",
        "token=SECRET_TOKEN_VALUE",
        "api_key: SECRET_TOKEN_VALUE",
        "github_pat_12345678901234567890",
        "ghp_12345678901234567890",
        "sk-12345678901234567890",
        "-----BEGIN PRIVATE KEY-----\nSECRET_TOKEN_VALUE\n-----END PRIVATE KEY-----",
        "child@example.test",
        "\x1b]8;;https://bad.test\x07hidden\x1b]8;;\x07",
        "https://user:SECRET_TOKEN_VALUE@example.test/path?token=SECRET_TOKEN_VALUE",
    ],
)
def test_secret_and_terminal_safety(dirty):
    clean = safe_text(dirty)
    assert "SECRET_TOKEN_VALUE" not in clean
    assert "child@example.test" not in clean
    assert "12345678901234567890" not in clean
    assert "\x1b" not in clean


def test_private_ui_file_is_out_of_band_and_exclusive(tmp_path, capsys):
    path = tmp_path / "observer.log"
    with HumanChannel(path=path) as channel:
        channel.write("Progress token=SECRET_TOKEN_VALUE")
    assert capsys.readouterr() == ("", "")
    assert "SECRET_TOKEN_VALUE" not in path.read_text()
    assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        HumanChannel(path=path)


def test_ui_refuses_symlinks_and_governance_paths(tmp_path):
    target = tmp_path / "target"
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        HumanChannel(path=link)
    with pytest.raises(ValueError, match="protected"):
        HumanChannel(path=tmp_path / ".agora" / "events.md")
    assert not target.exists()


def test_watch_local_heartbeats_no_agent_polling(tmp_path):
    s = snapshot(tmp_path)
    now = [0.0]
    calls = []
    stream = StringIO()

    def read():
        calls.append(now[0])
        return s

    def sleep(seconds):
        now[0] += seconds

    with HumanChannel(stream=stream) as channel:
        code = watch(read, channel, interval=1, duration=2, clock=lambda: now[0], sleep=sleep)
    assert code == 0
    assert calls == [0, 1, 2]
    assert stream.getvalue().count("Agora AI-SDLC | Observation") == 1
    assert stream.getvalue().count("not an executor heartbeat") == 2


@pytest.mark.parametrize("interval", [0, -1, 0.1, 61, float("nan"), float("inf")])
def test_watch_rejects_unbounded_or_busy_intervals(interval):
    with pytest.raises(ValueError):
        watch(lambda: pytest.fail("must not read"), HumanChannel(stream=StringIO()), interval=interval)


def test_watch_can_be_cancelled():
    def interrupt():
        raise KeyboardInterrupt

    assert watch(interrupt, HumanChannel(stream=StringIO())) == 130


def test_ui_limit_stops_logs_not_core_actions(monkeypatch):
    monkeypatch.setattr("agora_ai_sdlc.observation_ui.MAX_UI_BYTES", 300)
    stream = StringIO()
    with HumanChannel(stream=stream) as channel:
        channel.write("x" * 400)
        channel.event("start.prepared")
        assert channel.limited
    assert "output limit reached" in stream.getvalue()
    assert "executor" not in stream.getvalue()


def test_real_core_observation_does_not_mutate_governance(tmp_path, monkeypatch):
    from test_installer import base_config

    from agora_ai_sdlc.installer import apply

    root, home = tmp_path / "project", tmp_path / "home"
    monkeypatch.setenv("AGORA_HOME", str(home))
    apply(base_config(), root, home)
    before = {str(p.relative_to(root)): p.read_bytes() for p in (root / ".agora").rglob("*") if p.is_file()}
    s = collect(root, swarm="delivery", work="first-work")
    assert s["status"] == "observed", s["warnings"]
    assert s["work"]["state"] == "inception"
    assert s["usage"]["records"] == 0
    assert s["sessions"] == []
    after = {str(p.relative_to(root)): p.read_bytes() for p in (root / ".agora").rglob("*") if p.is_file()}
    assert before == after


def test_human_channel_redacts_multiline_private_key(tmp_path):
    stream = StringIO()
    with HumanChannel(stream=stream) as channel:
        channel.write("before\n-----BEGIN PRIVATE KEY-----\nTOP_SECRET\n-----END PRIVATE KEY-----\nafter")
    assert "TOP_SECRET" not in stream.getvalue()
    assert "before" in stream.getvalue()
    assert "after" in stream.getvalue()
