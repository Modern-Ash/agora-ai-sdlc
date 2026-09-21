"""Preview-first Starter profile bootstrap over supported Agora Core APIs."""

import json
import os
import re
import subprocess
from pathlib import Path

import yaml
from agora.markdown import read_markdown
from agora.model import (
    AddActorInput,
    AssignActorInput,
    CreateSwarmInput,
    CreateWorkInput,
    InitInput,
    InstallMethodInput,
)
from agora.workspace import AgoraWorkspace

from agora_ai_sdlc import profile_activation
from agora_ai_sdlc.depth_profiles import asset_root

SCHEMA = "agora-ai-sdlc/starter-bootstrap/v1"
PROFILE_SCHEMA = "agora-ai-sdlc/adoption-profile/v1"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
INTEGRATIONS = {"generic", "codex", "claude"}
EXECUTION_ROLES = ("architect", "builder", "operator")


class StarterError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def load_profile() -> dict:
    data = yaml.safe_load((asset_root("profiles") / "starter" / "profile.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA or data.get("id") != "starter":
        raise StarterError("starter.profile.invalid", "invalid Starter profile")
    method = read_markdown(asset_root("registry") / "methods" / "ai-sdlc" / "METHOD.md").attributes
    if data["method"] != {"id": method["id"], "version": method["version"]}:
        raise StarterError("starter.profile.pack", "Starter profile must pin the shipped Method Pack version")
    return data


def _slug(value: object, field: str) -> str:
    text = str(value) if value is not None else ""
    if not SLUG.fullmatch(text):
        raise StarterError("starter.config.slug", f"invalid {field}")
    return text


def validate_config(config: dict) -> dict:
    required = {"schema", "profile", "swarm", "objective", "work", "runtimes", "role_execution"}
    if not isinstance(config, dict) or set(config) != required or config.get("schema") != SCHEMA:
        raise StarterError("starter.config.fields", "invalid Starter bootstrap fields")
    if config["profile"] != "starter":
        raise StarterError("starter.config.profile", "profile must be 'starter'")
    swarm = _slug(config["swarm"], "swarm id")
    objective = str(config["objective"]).strip()
    work = config["work"]
    if not objective or not isinstance(work, dict) or set(work) != {"id", "title", "criteria"}:
        raise StarterError("starter.config.work", "objective and explicit work are required")
    work_id, title = _slug(work["id"], "work id"), str(work["title"]).strip()
    criteria = work["criteria"]
    if not title or not isinstance(criteria, list) or not criteria:
        raise StarterError("starter.config.work", "work title and criteria are required")
    normalized_criteria = []
    for item in criteria:
        if not isinstance(item, dict) or set(item) != {"id", "text"} or not str(item["text"]).strip():
            raise StarterError("starter.config.criteria", "each criterion needs id and text")
        normalized_criteria.append((_slug(item["id"], "criterion id"), str(item["text"]).strip()))
    if len({item[0] for item in normalized_criteria}) != len(normalized_criteria):
        raise StarterError("starter.config.criteria", "criterion ids must be unique")
    runtimes = config["runtimes"]
    maximum = int(load_profile()["topology"]["max_ai_runtimes"])
    if not isinstance(runtimes, list) or len(runtimes) > maximum:
        raise StarterError("starter.config.runtimes", f"Starter supports at most {maximum} AI runtimes")
    normalized_runtimes = []
    for runtime in runtimes:
        if not isinstance(runtime, dict) or set(runtime) != {"id", "integration", "provider", "model"}:
            raise StarterError("starter.config.runtime", "runtime fields are invalid")
        runtime_id = _slug(runtime["id"], "runtime id")
        if (
            runtime["integration"] not in INTEGRATIONS
            or not str(runtime["provider"]).strip()
            or not str(runtime["model"]).strip()
        ):
            raise StarterError("starter.config.runtime", f"invalid runtime {runtime_id!r}")
        normalized_runtimes.append({**runtime, "id": runtime_id})
    ids = [runtime["id"] for runtime in normalized_runtimes]
    if len(ids) != len(set(ids)):
        raise StarterError("starter.config.runtime", "runtime ids must be unique")
    execution = config["role_execution"]
    if not isinstance(execution, dict) or set(execution) != set(EXECUTION_ROLES):
        raise StarterError("starter.config.roles", "architect, builder, and operator execution are required")
    if any(value != "human" and value not in ids for value in execution.values()):
        raise StarterError("starter.config.roles", "role execution must reference human or a declared runtime")
    return {
        "schema": SCHEMA,
        "profile": "starter",
        "swarm": swarm,
        "objective": objective,
        "work": {"id": work_id, "title": title, "criteria": normalized_criteria},
        "runtimes": normalized_runtimes,
        "role_execution": {role: execution[role] for role in EXECUTION_ROLES},
    }


def preview(config: dict, target: Path) -> dict:
    normalized = validate_config(config)
    profile = load_profile()
    actors = [
        "product-owner",
        "quality-reviewer",
        "delivery-member",
        *[f"ai-{r['id']}" for r in normalized["runtimes"]],
    ]
    return {
        "schema": "agora-ai-sdlc/starter-preview/v1",
        "target": str(target.resolve()),
        "existing_repository": (target / ".git").is_dir(),
        "profile": profile["id"],
        "depth": profile["depth"],
        "method": profile["method"],
        "actors": actors,
        "assignments": {
            "product-owner": "product-owner",
            "quality-reviewer": "quality-reviewer",
            **{
                role: "delivery-member" if runtime == "human" else f"ai-{runtime}"
                for role, runtime in normalized["role_execution"].items()
            },
        },
        "swarm": normalized["swarm"],
        "work": normalized["work"]["id"],
        "writes": ["git repository if absent", ".agora project state", "AGORA_HOME state"],
    }


def apply(config: dict, target: Path, home: Path) -> dict:
    normalized = validate_config(config)
    plan = preview(config, target)
    target.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").is_dir():
        subprocess.run(["git", "init", "-q", str(target)], check=True)
    os.environ["AGORA_HOME"] = str(home.resolve())
    workspace = AgoraWorkspace(cwd=target)
    workspace.initialize(InitInput(integration="generic", provider="local", model="human", default_method="scrum"))
    installed = workspace.install_method(
        InstallMethodInput(source=str(asset_root("registry") / "methods" / "ai-sdlc"), scope="project")
    )
    if installed.version != plan["method"]["version"]:
        raise StarterError("starter.apply.pack", "installed Method Pack version differs from preview")
    actors = [
        AddActorInput("product-owner", "Product Owner", "human", ["specification"], "project"),
        AddActorInput("quality-reviewer", "Quality Reviewer", "human", ["review"], "project"),
        AddActorInput(
            "delivery-member", "Delivery Member", "human", ["specification", "implementation", "operations"], "project"
        ),
    ]
    actors.extend(
        AddActorInput(
            f"ai-{runtime['id']}",
            runtime["id"],
            "ai-agent",
            ["specification", "implementation", "operations"],
            "project",
            integration=runtime["integration"],
            provider=runtime["provider"],
            model=runtime["model"],
        )
        for runtime in normalized["runtimes"]
    )
    for actor in actors:
        workspace.add_actor(actor)
    workspace.create_swarm(
        CreateSwarmInput(
            id=normalized["swarm"], objective=normalized["objective"], method="ai-sdlc", create_branch=False
        )
    )
    for role, actor in plan["assignments"].items():
        workspace.assign_actor(AssignActorInput(swarm_id=normalized["swarm"], role_id=role, actor_id=actor))
    workspace.create_work(
        CreateWorkInput(
            swarm_id=normalized["swarm"], id=normalized["work"]["id"], title=normalized["work"]["title"],
            actor_id="product-owner", acceptance_criteria=normalized["work"]["criteria"],
        )
    )  # fmt: skip
    profile_activation.activate(workspace, normalized["swarm"], normalized["work"]["id"], "product-owner", "starter")
    validation = workspace.validate()
    work = workspace.show_work(normalized["swarm"], normalized["work"]["id"])
    return {**plan, "validate": "ok" if validation.ok else "failed", "work_state": work.state}


def interactive(config: dict, target: Path, home: Path, *, input_fn=input, output_fn=print) -> dict | None:
    plan = preview(config, target)
    output_fn(json.dumps(plan, sort_keys=True))
    if input_fn("Apply Starter bootstrap? [y/N] ").strip().casefold() not in {"y", "yes"}:
        return None
    return apply(config, target, home)
