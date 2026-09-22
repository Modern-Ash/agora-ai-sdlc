from types import SimpleNamespace

from agora_ai_sdlc.doctor import _validation_detail


def test_validation_detail_surfaces_bounded_actionable_codes():
    issues = [
        SimpleNamespace(code="swarm.status-stale", message="Forming swarm has every required role assigned"),
        SimpleNamespace(code="work.branch-mismatch", message="Current branch does not match recorded Work branch"),
        SimpleNamespace(code="artifact.invalid", message="Artifact contract is invalid"),
        SimpleNamespace(code="extra.issue", message="This item should be summarized"),
    ]
    validation = SimpleNamespace(ok=False, issues=issues)

    detail = _validation_detail(validation)

    assert detail.startswith("Agora validation failed — swarm.status-stale:")
    assert "work.branch-mismatch:" in detail
    assert "artifact.invalid:" in detail
    assert "+1 more" in detail
    assert "extra.issue" not in detail


def test_validation_detail_reports_valid_project():
    validation = SimpleNamespace(ok=True, issues=[])

    assert _validation_detail(validation) == "valid Agora project"
