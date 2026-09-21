import json

import pytest
import yaml
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.installer import (
    InstallerError,
    apply,
    load_config,
    preview,
    render_config,
    validate_config,
    wizard,
)


def base_config():
    return {
        "schema": "agora-ai-sdlc/install-config/v1",
        "project": {"id": "demo", "name": "Demo", "mode": "new"},
        "profile": "starter",
        "depth": "standard",
        "language": "java",
        "framework": "spring-boot",
        "pathway": "new-product",
        "integrations": ["github", "ci"],
        "runtimes": [],
        "role_execution": {
            "architect": "human",
            "builder": "human",
            "operator": "human",
        },
        "swarm": "delivery",
        "objective": "Deliver Demo",
        "work": {
            "id": "first-work",
            "title": "Deliver first outcome",
            "criteria": [{"id": "outcome", "text": "Outcome is implemented and reviewed"}],
        },
    }


def test_config_round_trip_is_deterministic(tmp_path):
    config = base_config()
    rendered = render_config(config)
    path = tmp_path / "install.yaml"
    path.write_text(rendered, encoding="utf-8")

    loaded = load_config(path)
    assert loaded == validate_config(config)
    assert yaml.safe_load(rendered)["language"] == "java"
    assert "credential" not in rendered.casefold()


def test_profile_rejects_weaker_depth_before_write(tmp_path):
    config = base_config()
    config["profile"] = "regulated"
    config["depth"] = "standard"

    with pytest.raises(InstallerError) as error:
        apply(config, tmp_path / "project", tmp_path / "home")

    assert error.value.code == "installer.depth"
    assert not (tmp_path / "project").exists()


def test_human_only_project_bootstraps_and_records_metadata(tmp_path, monkeypatch):
    target, home = tmp_path / "project", tmp_path / "home"
    result = apply(base_config(), target, home)

    monkeypatch.setenv("AGORA_HOME", str(home))
    workspace = AgoraWorkspace(cwd=target)

    assert result["validate"] == "ok"
    assert result["work_state"] == "readiness"
    assert workspace.validate().ok
    metadata = yaml.safe_load((target / "ai-sdlc" / "project.yaml").read_text(encoding="utf-8"))
    assert metadata["language"] == "java"
    assert metadata["framework"] == "spring-boot"
    assert metadata["integrations"] == ["github", "ci"]
    assert metadata["profile"] == "starter"
    assert metadata["depth"] == "standard"


def test_multi_runtime_project_assigns_roles_without_credentials(tmp_path):
    config = base_config()
    config["runtimes"] = [
        {
            "id": "planner",
            "integration": "claude",
            "provider": "anthropic",
            "model": "claude-sonnet",
        },
        {
            "id": "builder",
            "integration": "generic",
            "provider": "ollama",
            "model": "qwen3-coder",
        },
    ]
    config["role_execution"] = {
        "architect": "planner",
        "builder": "builder",
        "operator": "human",
    }

    target, home = tmp_path / "project", tmp_path / "home"
    result = apply(config, target, home)

    assert result["validate"] == "ok"
    serialized = json.dumps(config).casefold()
    assert config["runtimes"][0]["provider"] == "anthropic"
    assert config["runtimes"][0]["model"] == "claude-sonnet"
    assert config["runtimes"][1]["provider"] == "ollama"
    assert config["runtimes"][1]["model"] == "qwen3-coder"
    assert "api_key" not in serialized
    assert "password" not in serialized
    assert "token" not in serialized


def test_preview_is_read_only(tmp_path):
    target = tmp_path / "project"
    plan = preview(base_config(), target)

    assert not target.exists()
    assert plan["profile"] == "starter"
    assert plan["language"] == "java"
    assert plan["framework"] == "spring-boot"


def test_wizard_builds_config_without_writing_target(tmp_path):
    target = tmp_path / "sample-project"
    answers = iter(
        [
            "",  # project id
            "",  # project name
            "",  # starter
            "",  # standard
            "python",
            "fastapi",
            "",  # new-product
            "n",  # github
            "n",  # gitlab
            "n",  # jira
            "y",  # ci
            "n",  # security
            "n",  # observability
            "y",  # add runtime
            "primary",
            "generic",
            "ollama",
            "qwen3-coder",
            "n",  # another runtime
            "primary",
            "primary",
            "human",
            "",  # swarm
            "",  # objective
            "",  # work id
            "",  # work title
            "",  # criterion
        ]
    )

    config = wizard(target, input_fn=lambda _: next(answers), output_fn=lambda _: None)

    assert not target.exists()
    assert config["language"] == "python"
    assert config["framework"] == "fastapi"
    assert config["integrations"] == ["ci"]
    assert config["runtimes"][0]["provider"] == "ollama"
    assert config["role_execution"]["architect"] == "primary"
    assert config["role_execution"]["builder"] == "primary"
    assert config["role_execution"]["operator"] == "human"
