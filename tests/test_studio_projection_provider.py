import json
import re
from pathlib import Path
from types import SimpleNamespace

import agora.application
import pytest
from agora.model import SetActorRuntimeInput, StartSessionInput

from agora_ai_sdlc.flavor_manifest import load_packaged_manifest
from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle
from agora_ai_sdlc.studio_projection import (
    PROJECTION_SCHEMA,
    SECTION_ORDER,
    AiSdlcProjectionProvider,
    _metrics,
    _profiles,
    _separation,
    projector,
)

pytestmark = pytest.mark.skipif(
    not hasattr(agora.application, "FlavorProjectionContribution"),
    reason="flavor projection needs Agora Core >=0.9",
)

SELECTION = "selected-test0001"


@pytest.fixture
def life(tmp_path):
    life = Lifecycle(tmp_path / "project", tmp_path / "home")
    life.to_intent()
    return life


def read(life: Lifecycle):
    service = agora.application.AgoraReadService.from_path(life.root, flavor_projectors=(projector,))
    return service.flavor_projection(PROJECTION_SCHEMA, SELECTION, SWARM, WORK)


def payload(life: Lifecycle) -> dict:
    return read(life).to_dict()


def test_real_core_accepts_the_provider_and_validates_the_aggregate_against_its_schema(life):
    result = payload(life)
    assert result["schema"] == PROJECTION_SCHEMA
    assert result["project"]["selection_id"] == SELECTION
    assert re.fullmatch(r"[0-9a-f]{64}", result["project"]["snapshot"])
    assert result["lifecycle"]["status"] == "available"
    assert result["lifecycle"]["value"]["current_state"] == "intent"
    assert result["presentation"]["authoritative"] is False
    assert result["presentation"]["section_order"] == SECTION_ORDER


def test_flavor_section_comes_from_the_packaged_manifest(life):
    manifest = load_packaged_manifest()
    flavor = payload(life)["flavor"]
    assert flavor["status"] == "available"
    assert flavor["value"] == {
        "id": manifest.id,
        "name": manifest.name,
        "version": manifest.version,
        "manifest_schema": "agora/flavor/v1",
        "supported_core": manifest.supported_core,
    }


def test_missing_optional_core_facts_remain_explicitly_unavailable(life):
    result = payload(life)
    expected = {
        "profiles": "projection.profiles-unavailable",
        "separation": "projection.separation-unavailable",
        "provenance": "projection.provenance-unavailable",
    }
    for name, code in expected.items():
        assert result[name]["status"] == "unavailable"
        assert result[name]["reason"]["code"] == code
        assert "value" not in result[name]

    assert result["metrics"]["status"] in {"available", "unavailable"}


def test_profiles_use_core_selection_before_legacy_artifacts():
    context = SimpleNamespace(
        selection=SimpleNamespace(profile="lg-enterprise", depth="regulated"),
        work=SimpleNamespace(artifacts=()),
    )
    section = _profiles(context)
    assert section == {
        "status": "available",
        "value": [
            {
                "id": "lg-enterprise",
                "depth": "regulated",
                "active": True,
                "source": "core-selection",
            }
        ],
    }


def test_separation_requires_distinct_actor_and_current_digest():
    artifact = SimpleNamespace(
        uri="repo://src/app.py",
        kind="implementation",
        timestamp="2026-09-21T10:00:00Z",
        produced_by="project:developer",
        content_sha256="a" * 64,
    )
    review = SimpleNamespace(
        type="review",
        timestamp="2026-09-21T10:05:00Z",
        produced_by="project:reviewer",
        artifact_references=("repo://src/app.py",),
        artifact_content_sha256={"repo://src/app.py": "a" * 64},
    )
    context = SimpleNamespace(work=SimpleNamespace(artifacts=(artifact,), evidence=(review,)))
    section = _separation(context)
    assert section["status"] == "available"
    assert section["value"]["decision"] == "satisfied"
    assert section["value"]["blockers"] == []

    review.artifact_content_sha256["repo://src/app.py"] = "b" * 64
    stale = _separation(context)
    assert stale["value"]["decision"] == "blocked"
    assert stale["value"]["blockers"][0]["code"] == "separation.review-missing-or-stale"


def test_metrics_preserve_core_zero_and_measurement_provenance():
    metric = SimpleNamespace(
        key="usage.tokens",
        start="2026-09-21T00:00:00Z",
        end="2026-09-21T23:59:59Z",
        value=0,
        count=0,
        status="available",
        source_refs=(),
        measurement="measured",
    )
    section = _metrics(SimpleNamespace(metrics=(metric,)))
    assert section["status"] == "available"
    assert section["value"]["items"] == [
        {
            "id": "usage.tokens",
            "value": 0,
            "unit": "units",
            "source": "measured",
            "status": "available",
            "count": 0,
            "source_refs": [],
        }
    ]


def test_session_provenance_maps_core_bases_without_upgrading_trust(life):
    life.ws.start_session(
        StartSessionInput(id="build-1", actor_id="build", swarm_id=SWARM, work_id=WORK, runtime_version="1.2.3")
    )
    section = payload(life)["provenance"]
    assert section["status"] == "available"
    (execution,) = section["value"]["executions"]
    assert execution["session_id"] == "build-1" and execution["actor"] == "project:build"
    for field in ("runtime", "provider", "model"):
        assert execution[field]["source"] == "declared" and execution[field]["value"]
    assert execution["runtime_version"] == {"source": "declared", "value": "1.2.3"}
    assert execution["selection_reason"]["source"] == "declared"
    assert execution["fallback"] == {"source": "declared", "used": False, "from": None, "reason": None}
    assert not any(field["source"] == "observed" for field in execution.values() if isinstance(field, dict))


def test_fallback_selection_is_projected_with_its_origin_and_reason(life, monkeypatch):
    monkeypatch.setattr("agora.workspace.shutil.which", lambda name: "/usr/bin/claude" if name == "claude" else None)
    life.ws.set_actor_runtime(
        SetActorRuntimeInput(
            actor_id="build",
            integration="codex",
            provider="openai",
            model="primary",
            fallbacks=["claude:anthropic:fallback-model"],
        )
    )
    life.ws.start_session(StartSessionInput(id="fallback-1", actor_id="build", swarm_id=SWARM, work_id=WORK))
    (execution,) = payload(life)["provenance"]["value"]["executions"]
    assert execution["fallback"]["used"] is True
    assert execution["fallback"]["from"] == {"runtime": "codex", "provider": "openai", "model": "primary"}
    assert execution["fallback"]["reason"] == "fallback-executable-unavailable"
    assert execution["runtime"]["value"] == "claude"


def test_legacy_session_without_provenance_is_never_reported_as_observed(life):
    life.ws.start_session(StartSessionInput(id="legacy-1", actor_id="build", swarm_id=SWARM, work_id=WORK))
    session_file = Path(life.ws.show_session("legacy-1").path) / "SESSION.md"
    session_file.write_text(
        "\n".join(
            line for line in session_file.read_text(encoding="utf-8").splitlines() if not line.startswith("provenance-")
        )
        + "\n",
        encoding="utf-8",
    )
    (execution,) = payload(life)["provenance"]["value"]["executions"]
    assert execution["runtime_version"] == {"source": "unavailable", "value": None}
    assert execution["selection_reason"] == {"source": "unavailable", "value": None}
    assert execution["fallback"]["source"] == "unavailable" and execution["fallback"]["used"] is None


def test_snapshot_changes_with_durable_state_and_output_has_no_paths_or_secrets(life):
    before = payload(life)
    life.to_inception()
    after = payload(life)
    assert before["project"]["snapshot"] != after["project"]["snapshot"]
    assert after["lifecycle"]["value"]["current_state"] == "inception"
    text = json.dumps(after)
    assert str(life.root) not in text and "PRIVATE KEY" not in text


def test_provider_is_reusable_and_instances_declare_the_contract():
    assert isinstance(projector, AiSdlcProjectionProvider)
    assert projector.projection_schema == PROJECTION_SCHEMA
    assert projector.required_sections == ("flavor", "profiles", "provenance", "separation", "metrics")
    assert projector.projection_schema_document["properties"]["schema"]["const"] == PROJECTION_SCHEMA
