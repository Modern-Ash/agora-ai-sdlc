import json
from itertools import pairwise
from pathlib import Path

import pytest
import yaml
from support.lifecycle import Lifecycle

from agora_ai_sdlc.cli import main
from agora_ai_sdlc.depth_profiles import (
    DEFAULT,
    FIELDS,
    ORDER,
    ProfileError,
    assess,
    asset_root,
    baseline,
    is_monotonic,
    recommend,
    resolve,
)  # fmt: skip

FIXTURES = Path(__file__).parent / "fixtures" / "depth"


@pytest.mark.parametrize("depth", ORDER)
def test_resolved_obligation_snapshots(depth):
    assert resolve(depth).snapshot() == json.loads((FIXTURES / f"{depth}.json").read_text())


def test_standard_is_default_and_equals_pack_baseline():
    assert DEFAULT == "standard"
    assert resolve().id == "standard"
    assert {g: {k: tuple(v) for k, v in f.items()} for g, f in resolve().gates.items()} == baseline()


def test_resolution_is_deterministic():
    assert [resolve(d).snapshot() for d in ORDER] == [resolve(d).snapshot() for d in ORDER]


def test_monotonic_across_all_depths():
    profiles = [resolve(d) for d in ORDER]
    for lower, higher in pairwise(profiles):
        assert is_monotonic(lower, higher), (lower.id, higher.id)
    assert not is_monotonic(resolve("standard"), resolve("minimal"))


def test_only_minimal_removes_and_it_is_justified():
    for depth in ORDER:
        data = yaml.safe_load((asset_root("profiles") / "depth" / f"{depth}.yaml").read_text())
        if data.get("remove"):
            assert depth == "minimal" and data["remove"]["justification"].strip()


def test_human_ownership_of_intent_holds_at_every_depth():
    for depth in ORDER:
        assert "product-owner" in resolve(depth).gates["intent-framed"]["approvals"]


def test_regulated_requires_signed_actions_and_human_final_approval():
    assert resolve("regulated").requires == {"signed-actions": True, "human-final-approval": True}
    assert "governance-owner" in resolve("regulated").gates["completion"]["approvals"]
    assert resolve("comprehensive").requires == {}


def test_protected_removal_and_unjustified_removal_rejected(tmp_path, monkeypatch):
    root = tmp_path
    (root / "profiles" / "depth").mkdir(parents=True)
    for depth in ORDER:
        (root / "profiles" / "depth" / f"{depth}.yaml").write_text(
            (asset_root("profiles") / "depth" / f"{depth}.yaml").read_text()
        )
    (root / "registry").symlink_to(asset_root("registry"))
    monkeypatch.setattr("agora_ai_sdlc.depth_profiles.asset_root", lambda name: root / name)
    path = root / "profiles" / "depth" / "minimal.yaml"
    path.write_text(
        "schema: agora-ai-sdlc/depth-profile/v1\nid: minimal\nextends: standard\nremove:\n  justification: x\n"
        "  gates:\n    intent-framed:\n      approvals: [product-owner]\n"
    )
    with pytest.raises(ProfileError) as exc:
        resolve("minimal")
    assert exc.value.code == "profile.protected"
    path.write_text(
        "schema: agora-ai-sdlc/depth-profile/v1\nid: minimal\nextends: standard\nremove:\n"
        "  gates:\n    completion:\n      evidence: [security-scan]\n"
    )
    with pytest.raises(ProfileError) as exc:
        resolve("minimal")
    assert exc.value.code == "profile.unjustified"


@pytest.mark.parametrize("bad", ["nope", "", "STANDARD", "../standard"])
def test_unknown_profile_fails(bad):
    with pytest.raises(ProfileError) as exc:
        resolve(bad)
    assert exc.value.code == "profile.unknown"


def test_cli_prints_snapshot_and_rejects_unknown(capsys):
    assert main(["profile", "regulated"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "regulated"
    assert main(["profile", "nope"]) == 2
    assert "profile.unknown" in capsys.readouterr().err


def test_assess_is_read_only_and_reports_missing():
    result = assess("comprehensive", "architecture-approved", {"requirements", "architecture"}, set(), set())
    assert result["missing"]["artifacts"] == ["domain-model", "threat-model"]
    assert "missing" in assess("standard", "completion", set(), set(), set())
    assert assess("standard", "intent-framed", {"intent"}, set(), {"product-owner"})["missing"] == {}
    with pytest.raises(ProfileError):
        assess("standard", "no-such-gate", set(), set(), set())


def test_mid_work_stricter_depth_exposes_gaps_without_corrupting_work(tmp_path, monkeypatch):
    life = Lifecycle(tmp_path / "project", tmp_path / "home", monkeypatch)
    life.to_intent()
    life.to_inception()
    life.stage("arch", "designed")
    life.artifact("arch", "architecture")
    life.artifact("arch", "requirements")
    life.approve("arch", "architect")
    life.clarify()
    before = life.ws.show_work("delivery", "feature")
    kinds, approvals = set(before.artifact_kinds), set(before.approval_roles)
    assert assess("standard", "architecture-approved", kinds, set(), approvals)["missing"] == {}
    stricter = assess("comprehensive", "architecture-approved", kinds, set(), approvals)
    assert stricter["missing"]["artifacts"] == ["domain-model", "threat-model"]
    after = life.ws.show_work("delivery", "feature")
    assert (after.state, after.artifact_kinds, after.approval_roles) == (
        before.state, before.artifact_kinds, before.approval_roles,
    )  # fmt: skip
    assert life.move("arch", "construction") == "construction"  # Core still enforces the baseline only


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        (("low", "reversible", "internal", "low"), "minimal"),
        (("medium", "reversible", "internal", "low"), "standard"),
        (("low", "hard", "public", "low"), "standard"),
        (("high", "reversible", "internal", "low"), "comprehensive"),
        (("low", "irreversible", "public", "low"), "comprehensive"),
        (("low", "reversible", "confidential", "low"), "comprehensive"),
        (("low", "reversible", "regulated", "low"), "regulated"),
    ],
)
def test_recommend_depth(criteria, expected):
    assert recommend(*criteria) == expected


def test_recommend_rejects_bad_criteria():
    with pytest.raises(ProfileError):
        recommend("extreme", "reversible", "internal", "low")
    assert set(FIELDS) == {"artifacts", "evidence", "approvals"}
