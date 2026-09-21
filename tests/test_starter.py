import json
import subprocess
from pathlib import Path

import pytest
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.starter import StarterError, apply, interactive, load_profile, preview

CONFIG = Path(__file__).parents[1] / "samples" / "starter" / "config.json"


def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_manifest_pins_shipped_pack_and_standard_profile():
    profile = load_profile()
    assert profile["depth"] == "standard"
    assert profile["method"] == {"id": "ai-sdlc", "version": "0.1.1"}
    assert profile["human_roles"] == ["product-owner", "quality-reviewer"]


def test_preview_is_deterministic_and_writes_nothing(tmp_path):
    target = tmp_path / "not-created"
    first = preview(config(), target)
    second = preview(config(), target)
    assert first == second and not target.exists()
    assert first["method"] == {"id": "ai-sdlc", "version": "0.1.1"}


def test_interactive_cancel_writes_nothing_to_target_or_home(tmp_path):
    target, home = tmp_path / "project", tmp_path / "home"
    output = []
    result = interactive(config(), target, home, input_fn=lambda _: "no", output_fn=output.append)
    assert result is None and len(output) == 1
    assert not target.exists() and not home.exists()


@pytest.mark.parametrize("existing", [False, True])
def test_bootstrap_fresh_and_existing_repository_validates_and_starts_first_work(tmp_path, monkeypatch, existing):
    target, home = tmp_path / "project", tmp_path / "home"
    if existing:
        target.mkdir()
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        (target / "keep.txt").write_text("keep\n", encoding="utf-8")
    result = apply(config(), target, home)
    monkeypatch.setenv("AGORA_HOME", str(home))
    workspace = AgoraWorkspace(cwd=target)
    assert result["validate"] == "ok" and result["work_state"] == "readiness"
    assert workspace.validate().ok
    assert workspace.show_work("starter-team", "first-work").state == "readiness"
    assert (not existing) or (target / "keep.txt").read_text(encoding="utf-8") == "keep\n"


def test_human_only_execution_is_supported(tmp_path):
    data = config()
    data["runtimes"] = []
    data["role_execution"] = {role: "human" for role in ("architect", "builder", "operator")}
    result = apply(data, tmp_path / "project", tmp_path / "home")
    assert result["validate"] == "ok"
    assert set(result["assignments"].values()) == {"product-owner", "quality-reviewer", "delivery-member"}


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda data: data.update(profile="enterprise"), "starter.config.profile"),
        (
            lambda data: data["runtimes"].append(
                {"id": "third", "integration": "generic", "provider": "p", "model": "m"}
            ),
            "starter.config.runtimes",
        ),
        (lambda data: data["runtimes"][0].update(integration="unknown"), "starter.config.runtime"),
        (lambda data: data["role_execution"].update(builder="missing"), "starter.config.roles"),
    ],
)
def test_invalid_profile_runtime_and_assignment_fail_before_write(tmp_path, mutation, code):
    data = config()
    if code == "starter.config.runtimes":
        data["runtimes"].append({"id": "second", "integration": "generic", "provider": "p", "model": "m"})
    mutation(data)
    with pytest.raises(StarterError) as error:
        apply(data, tmp_path / "project", tmp_path / "home")
    assert error.value.code == code
    assert not (tmp_path / "project").exists() and not (tmp_path / "home").exists()


def test_noninteractive_cli_uses_explicit_config(tmp_path, capsys):
    from agora_ai_sdlc.cli import main

    assert (
        main(
            [
                "starter-bootstrap",
                "--config",
                str(CONFIG),
                "--target",
                str(tmp_path / "p"),
                "--home",
                str(tmp_path / "h"),
                "--yes",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["validate"] == "ok" and result["work_state"] == "readiness"


def test_config_has_no_credentials_or_external_install_directives():
    data = config()
    assert set(data) == {"schema", "profile", "swarm", "objective", "work", "runtimes", "role_execution"}
    assert "credential" not in json.dumps(data).casefold()
