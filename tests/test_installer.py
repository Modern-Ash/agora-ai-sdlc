import json
import subprocess

import pytest
import yaml
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc.installer import (
    InstallerError,
    apply,
    core_preflight,
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
            "developer": "human",
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
    assert result["work_state"] == "inception"
    assert workspace.validate().ok
    metadata = yaml.safe_load((target / "ai-sdlc" / "project.yaml").read_text(encoding="utf-8"))
    assert metadata["language"] == "java"
    assert metadata["framework"] == "spring-boot"
    assert metadata["integrations"] == ["github", "ci"]
    assert metadata["profile"] == "starter"
    assert metadata["depth"] == "standard"
    assert metadata["runtimes"] == []
    assert metadata["role_execution"] == {"developer": "human"}
    assert metadata["method"] == {"id": "ai-sdlc", "version": "0.2.0"}
    installed_method = yaml.safe_load(
        (target / ".agora" / "methods" / "ai-sdlc" / "METHOD.md").read_text(encoding="utf-8").split("---", 2)[1]
    )
    assert installed_method["version"] == "0.2.0"
    assert installed_method["work-states"] == ["inception", "construction", "operations", "completed"]
    skill = target / ".agora" / "skills" / "agora-ai-sdlc-guided" / "SKILL.md"
    assert skill.is_file()
    assert "Never record a human approval without explicit confirmation" in skill.read_text(encoding="utf-8")
    assert (target / ".agora" / "tools" / "github-issues" / "TOOL.md").is_file()


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
        "developer": "builder",
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
    assert config["role_execution"]["developer"] == "primary"


def test_core_preflight_reports_installed_core_and_cli(monkeypatch):
    monkeypatch.setattr("agora_ai_sdlc.installer.installed_core_version", lambda: "0.9.0")
    monkeypatch.setattr("agora_ai_sdlc.installer.check_core_compatibility", lambda manifest, installed=None: None)
    monkeypatch.setattr(
        "agora_ai_sdlc.installer.shutil.which", lambda name: "/venv/bin/agora" if name == "agora" else None
    )

    result = core_preflight()

    assert result == {"version": "0.9.0", "executable": "/venv/bin/agora"}


def test_core_preflight_fails_when_cli_is_missing(monkeypatch):
    monkeypatch.setattr("agora_ai_sdlc.installer.installed_core_version", lambda: "0.9.0")
    monkeypatch.setattr("agora_ai_sdlc.installer.check_core_compatibility", lambda manifest, installed=None: None)
    monkeypatch.setattr("agora_ai_sdlc.installer.shutil.which", lambda name: None)

    with pytest.raises(InstallerError) as error:
        core_preflight()

    assert error.value.code == "installer.core.cli-missing"


def test_core_preflight_fails_when_core_is_incompatible(monkeypatch):
    from agora_ai_sdlc.flavor_manifest import ManifestError

    monkeypatch.setattr("agora_ai_sdlc.installer.installed_core_version", lambda: "9.9.9")

    def incompatible(manifest, installed=None):
        raise ManifestError("manifest.core_incompatible", "unsupported Core")

    monkeypatch.setattr("agora_ai_sdlc.installer.check_core_compatibility", incompatible)

    with pytest.raises(InstallerError) as error:
        core_preflight()

    assert error.value.code == "installer.core.incompatible"


def test_apply_reports_core_handoff_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agora_ai_sdlc.installer.core_preflight",
        lambda: {"version": "0.9.0", "executable": "/venv/bin/agora"},
    )

    result = apply(base_config(), tmp_path / "project", tmp_path / "home")

    assert result["core_validation"] == "ok"
    assert result["next_commands"] == [
        "agora validate",
        "agora status --board",
        "agora-ai-sdlc continue",
    ]


def test_wizard_displays_detected_runtimes_without_enabling_them(tmp_path, monkeypatch):
    from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery

    detected = (
        RuntimeDiscovery(
            id="codex",
            name="Codex",
            command="codex",
            installed=True,
            executable="/bin/codex",
            responsive=True,
            version="codex 1.0",
            configured=False,
        ),
    )
    monkeypatch.setattr("agora_ai_sdlc.installer.discover_runtimes", lambda target: detected)
    outputs = []
    answers = iter(
        [
            "",
            "",
            "",
            "",
            "python",
            "",
            "",
            "n",
            "n",
            "n",
            "n",
            "n",
            "n",
            "n",
            "human",
            "",
            "",
            "",
            "",
            "",
        ]
    )

    config = wizard(tmp_path / "project", input_fn=lambda _: next(answers), output_fn=outputs.append)

    assert config["runtimes"] == []
    assert any("Codex" in output and "responsive" in output for output in outputs)
    assert any("does not configure" in output for output in outputs)


def test_legacy_execution_roles_migrate_when_executor_is_shared():
    config = base_config()
    config["role_execution"] = {
        "architect": "human",
        "builder": "human",
        "operator": "human",
    }

    normalized = validate_config(config)

    assert normalized["role_execution"] == {"developer": "human"}
    assert normalized["method"] == {"id": "ai-sdlc", "version": "0.2.0"}


def test_legacy_execution_roles_fail_when_executors_differ():
    config = base_config()
    config["runtimes"] = [
        {"id": "planner", "integration": "generic", "provider": "local", "model": "planner"},
        {"id": "builder", "integration": "generic", "provider": "local", "model": "builder"},
    ]
    config["role_execution"] = {
        "architect": "planner",
        "builder": "builder",
        "operator": "human",
    }

    with pytest.raises(InstallerError) as error:
        validate_config(config)

    assert error.value.code == "installer.roles_migration"


def test_method_metadata_revalidates_but_rejects_other_versions():
    normalized = validate_config(base_config())
    assert validate_config(normalized)["method"] == {"id": "ai-sdlc", "version": "0.2.0"}

    normalized["method"] = {"id": "ai-sdlc", "version": "0.1.1"}
    with pytest.raises(InstallerError) as error:
        validate_config(normalized)

    assert error.value.code == "installer.method"


def test_quality_reviewer_actor_is_optional_and_not_required_assignment(tmp_path, monkeypatch):
    target, home = tmp_path / "project", tmp_path / "home"
    apply(base_config(), target, home)

    monkeypatch.setenv("AGORA_HOME", str(home))
    workspace = AgoraWorkspace(cwd=target)
    actors = {actor.id: actor for actor in workspace.list_actors()}
    swarm = workspace.show_swarm("delivery")

    assert "quality-reviewer" in actors
    assert "quality-reviewer" not in swarm.required_roles
    assert "developer" in swarm.required_roles



def test_preview_treats_linked_git_worktree_as_existing_repository(tmp_path):
    primary = tmp_path / "primary"
    primary.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=primary, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "agora@example.test"], cwd=primary, check=True)
    subprocess.run(["git", "config", "user.name", "Agora Test"], cwd=primary, check=True)
    (primary / "README.md").write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=primary, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=primary, check=True, capture_output=True)

    linked = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", str(linked), "main"], cwd=primary, check=True, capture_output=True)

    config = base_config()
    config["project"]["mode"] = "existing"
    config["pathway"] = "brownfield"
    plan = preview(config, linked)

    assert (linked / ".git").is_file()
    assert plan["existing_repository"] is True
