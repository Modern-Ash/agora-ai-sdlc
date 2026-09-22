from agora_ai_sdlc.progress import lifecycle_progress, start_progress


def test_start_progress_is_deterministic_and_reaches_100_percent():
    codes = (
        "start.inspect",
        "start.runtime-ready",
        "start.work-ready",
        "start.issue-read",
        "start.intent-ready",
        "start.pathway",
        "start.handoff",
        "start.prepared",
    )

    rendered = [start_progress(code, code) for code in codes]

    assert rendered[0] == "[█░░░░░░░░░]  12%  1/8  start.inspect"
    assert rendered[-1] == "[██████████] 100%  8/8  start.prepared"


def test_reused_issue_read_advances_same_progress_step():
    fresh = start_progress("start.issue-read", "fresh")
    reused = start_progress("start.issue-reused", "reused")

    assert fresh is not None and reused is not None
    assert "4/8" in fresh
    assert "4/8" in reused


def test_lifecycle_progress_represents_durable_stage_position_only():
    assert lifecycle_progress("inception") == "[██░░░░░░░░] 1/4  inception"
    assert lifecycle_progress("construction") == "[█████░░░░░] 2/4  construction"
    assert lifecycle_progress("operations") == "[████████░░] 3/4  operations"
    assert lifecycle_progress("completed") == "[██████████] 4/4  completed"
    assert "?/4" in lifecycle_progress(None)
