import json

import pytest

from agora_ai_sdlc.progress_events import (
    ProgressEmitter,
    ProgressEvent,
    legacy_callback,
    render_chat,
    render_jsonl,
    render_tty,
)


def test_event_contract_is_versioned_and_monotonic():
    emitter = ProgressEmitter(swarm="delivery", work="issue-295", revision=3)

    first = emitter.event("context", "started", "context-selection", "context.selecting")
    second = emitter.event(
        "decision",
        "completed",
        "system1",
        "decision.laya_resolved",
        facts={"summary": "Laya resolved decision locally", "generative_call": False},
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert second.snapshot()["schema"] == "agora-ai-sdlc/progress-event/v1"
    assert second.snapshot()["work"] == {"swarm": "delivery", "id": "issue-295", "revision": 3}


def test_same_event_renders_for_tty_chat_and_jsonl_without_changing_semantics():
    event = ProgressEvent(
        sequence=1,
        kind="routing",
        status="completed",
        stage="runtime-selection",
        message_key="routing.local_selected",
        facts={"summary": "Local/free executor selected", "tier": "local"},
    )

    assert render_tty(event) == "✓ Agora Flow · Local/free executor selected"
    assert render_chat(event) == "✓ Agora Flow · Local/free executor selected"
    payload = json.loads(render_jsonl(event))
    assert payload["facts"]["tier"] == "local"
    assert "\x1b" not in render_jsonl(event)


def test_started_tty_uses_spinner_but_chat_is_durable():
    event = ProgressEvent(1, "execution", "started", "executor", "executor.starting")

    assert render_tty(event, spinner="⠙").startswith("⠙ Agora Flow")
    assert render_chat(event).startswith("… Agora Flow")


def test_event_rejects_unknown_kind_status_and_visibility():
    with pytest.raises(ValueError):
        ProgressEvent(1, "secret", "started", "x", "x")
    with pytest.raises(ValueError):
        ProgressEvent(1, "result", "thinking", "x", "x")
    with pytest.raises(ValueError):
        ProgressEvent(1, "result", "completed", "x", "x", visibility="private-reasoning")


def test_progress_facts_do_not_require_provider_output_or_prompt():
    event = ProgressEvent(
        1,
        "gate",
        "blocked",
        "human-boundary",
        "gate.human_required",
        facts={"summary": "Human approval required", "completed": 3, "total": 7},
    )

    payload = event.snapshot()
    assert payload["facts"] == {"summary": "Human approval required", "completed": 3, "total": 7}
    assert "prompt" not in payload["facts"]
    assert "stdout" not in payload["facts"]


def test_legacy_callback_maps_existing_progress_without_changing_execution_api():
    events = []
    callback = legacy_callback(
        ProgressEmitter(swarm="delivery", work="w"),
        events.append,
    )

    callback("context")
    callback("executor_wait:tests running")

    assert [event.sequence for event in events] == [1, 2]
    assert events[0].kind == "context"
    assert events[1].status == "progress"
    assert events[1].facts["summary"] == "tests running"


def test_progress_event_snapshot_does_not_expose_private_reasoning_fields():
    event = ProgressEvent(
        1,
        "decision",
        "completed",
        "system1",
        "decision.resolved",
        facts={"summary": "Decision resolved", "confidence": 0.97},
    )

    serialized = render_jsonl(event)

    assert "chain_of_thought" not in serialized
    assert "prompt" not in serialized
    assert "stderr" not in serialized
