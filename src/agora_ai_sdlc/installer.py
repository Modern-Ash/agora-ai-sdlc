"""Interactive and reproducible project installer for Agora AI-SDLC."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml
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
from agora_ai_sdlc.depth_profiles import ORDER as DEPTH_ORDER
from agora_ai_sdlc.depth_profiles import asset_root
from agora_ai_sdlc.flavor_manifest import (
    ManifestError,
    check_core_compatibility,
    installed_core_version,
    load_packaged_manifest,
)
from agora_ai_sdlc.guided import skill_path
from agora_ai_sdlc.profile_activation import adoption_profiles
from agora_ai_sdlc.runtime_discovery import discover_runtimes, render_runtimes

SCHEMA = "agora-ai-sdlc/install-config/v1"
PROJECT_SCHEMA = "agora-ai-sdlc/project-config/v1"
INTEGRATIONS = ("generic", "codex", "claude")
PROFILE_IDS = ("starter", "enterprise", "modernization", "regulated")
METHOD_ID = "ai-sdlc"
METHOD_VERSION = "0.2.0"
EXECUTION_ROLES = ("developer",)
LEGACY_EXECUTION_ROLES = ("architect", "builder", "operator")
OPTIONAL_INTEGRATIONS = ("github", "gitlab", "jira", "ci", "security", "observability")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class InstallerError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _slug(value: object, field: str) -> str:
    text = str(value or "").strip()
    if SLUG.fullmatch(text) is None:
        raise InstallerError("installer.slug", f"invalid {field}")
    return text


def _text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise InstallerError("installer.text", f"{field} is required")
    return text


def _profile_default_depth(profile: str) -> str:
    profiles = adoption_profiles()
    if profile not in profiles:
        raise InstallerError("installer.profile", f"unsupported profile {profile!r}")
    return profiles[profile]


def _depth_at_least(selected: str, minimum: str) -> bool:
    return DEPTH_ORDER.index(selected) >= DEPTH_ORDER.index(minimum)


def core_preflight() -> dict[str, str]:
    """Verify that the Core package and CLI required by AI-SDLC are usable."""

    try:
        version = installed_core_version()
        check_core_compatibility(load_packaged_manifest(), installed=version)
    except ManifestError as error:
        raise InstallerError("installer.core.incompatible", str(error)) from error

    executable = shutil.which("agora")
    if executable is None:
        raise InstallerError(
            "installer.core.cli-missing",
            "Agora Core is installed as a dependency but the 'agora' executable is not available "
            "in the current environment; reinstall agora-ai-sdlc in the active environment",
        )
    return {"version": version, "executable": executable}


def validate_config(config: dict) -> dict:
    if not isinstance(config, dict) or config.get("schema") != SCHEMA:
        raise InstallerError("installer.schema", f"expected schema {SCHEMA}")

    allowed = {
        "schema",
        "project",
        "profile",
        "depth",
        "language",
        "framework",
        "pathway",
        "integrations",
        "runtimes",
        "role_execution",
        "swarm",
        "objective",
        "work",
    }
    unknown = set(config) - allowed
    if unknown:
        raise InstallerError("installer.fields", f"unknown fields: {', '.join(sorted(unknown))}")

    project = config.get("project")
    if not isinstance(project, dict):
        raise InstallerError("installer.project", "project mapping is required")
    project_id = _slug(project.get("id"), "project id")
    project_name = _text(project.get("name"), "project name")
    mode = project.get("mode", "existing")
    if mode not in {"new", "existing"}:
        raise InstallerError("installer.project", "project mode must be new or existing")

    profile = str(config.get("profile", "starter"))
    if profile not in PROFILE_IDS:
        raise InstallerError("installer.profile", f"profile must be one of {', '.join(PROFILE_IDS)}")
    minimum_depth = _profile_default_depth(profile)
    depth = str(config.get("depth") or minimum_depth)
    if depth not in DEPTH_ORDER or not _depth_at_least(depth, minimum_depth):
        raise InstallerError(
            "installer.depth",
            f"{profile} requires depth {minimum_depth} or stronger; got {depth}",
        )

    language = _text(config.get("language"), "primary language")
    framework = str(config.get("framework") or "").strip() or None
    pathway = str(config.get("pathway") or ("brownfield" if mode == "existing" else "new-product"))
    allowed_pathways = {
        "new-product",
        "brownfield",
        "refactor",
        "regulated-change",
        "scaling",
        "trivial-change",
    }
    if pathway not in allowed_pathways:
        raise InstallerError("installer.pathway", f"unsupported pathway {pathway!r}")

    integrations = config.get("integrations", [])
    if not isinstance(integrations, list) or any(item not in OPTIONAL_INTEGRATIONS for item in integrations):
        raise InstallerError("installer.integrations", "integrations contain unsupported values")
    integrations = list(dict.fromkeys(integrations))

    runtimes = config.get("runtimes", [])
    if not isinstance(runtimes, list):
        raise InstallerError("installer.runtimes", "runtimes must be a list")
    normalized_runtimes = []
    for runtime in runtimes:
        if not isinstance(runtime, dict):
            raise InstallerError("installer.runtime", "runtime must be a mapping")
        runtime_id = _slug(runtime.get("id"), "runtime id")
        integration = str(runtime.get("integration") or "")
        provider = _text(runtime.get("provider"), f"provider for {runtime_id}")
        model = _text(runtime.get("model"), f"model for {runtime_id}")
        if integration not in INTEGRATIONS:
            raise InstallerError(
                "installer.runtime",
                f"integration for {runtime_id!r} must be one of {', '.join(INTEGRATIONS)}",
            )
        normalized_runtimes.append(
            {
                "id": runtime_id,
                "integration": integration,
                "provider": provider,
                "model": model,
            }
        )
    runtime_ids = [item["id"] for item in normalized_runtimes]
    if len(runtime_ids) != len(set(runtime_ids)):
        raise InstallerError("installer.runtime", "runtime ids must be unique")

    role_execution = config.get("role_execution")
    if not isinstance(role_execution, dict):
        raise InstallerError("installer.roles", "role_execution must be a mapping")

    if set(role_execution) == set(LEGACY_EXECUTION_ROLES):
        executors = {role_execution[role] for role in LEGACY_EXECUTION_ROLES}
        if len(executors) != 1:
            raise InstallerError(
                "installer.roles_migration",
                "AI-SDLC 0.2.0 replaces architect/builder/operator with developer; "
                "legacy role_execution can migrate only when all three roles use the same executor",
            )
        role_execution = {"developer": executors.pop()}
    elif set(role_execution) != set(EXECUTION_ROLES):
        raise InstallerError(
            "installer.roles",
            "role_execution must define developer",
        )

    for role, executor in role_execution.items():
        if executor != "human" and executor not in runtime_ids:
            raise InstallerError(
                "installer.roles",
                f"{role} must reference human or a declared runtime",
            )

    swarm = _slug(config.get("swarm", "delivery"), "swarm id")
    objective = _text(config.get("objective"), "objective")
    work = config.get("work")
    if not isinstance(work, dict):
        raise InstallerError("installer.work", "work mapping is required")
    work_id = _slug(work.get("id"), "work id")
    title = _text(work.get("title"), "work title")
    criteria = work.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise InstallerError("installer.work", "at least one acceptance criterion is required")
    normalized_criteria = []
    for item in criteria:
        if isinstance(item, dict):
            criterion_id = item.get("id")
            criterion_text = item.get("text")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            criterion_id, criterion_text = item
        else:
            raise InstallerError(
                "installer.criteria",
                "criterion must be a mapping or normalized id/text pair",
            )
        normalized_criteria.append(
            (
                _slug(criterion_id, "criterion id"),
                _text(criterion_text, "criterion text"),
            )
        )
    if len({item[0] for item in normalized_criteria}) != len(normalized_criteria):
        raise InstallerError("installer.criteria", "criterion ids must be unique")

    return {
        "schema": SCHEMA,
        "project": {"id": project_id, "name": project_name, "mode": mode},
        "profile": profile,
        "depth": depth,
        "language": language,
        "framework": framework,
        "pathway": pathway,
        "integrations": integrations,
        "runtimes": normalized_runtimes,
        "role_execution": {role: role_execution[role] for role in EXECUTION_ROLES},
        "method": {"id": METHOD_ID, "version": METHOD_VERSION},
        "swarm": swarm,
        "objective": objective,
        "work": {"id": work_id, "title": title, "criteria": normalized_criteria},
    }


def load_config(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise InstallerError("installer.config", f"cannot read {path}") from error
    return validate_config(data)


def render_config(config: dict) -> str:
    normalized = validate_config(config)
    serializable = {
        **normalized,
        "work": {
            **normalized["work"],
            "criteria": [{"id": item_id, "text": text} for item_id, text in normalized["work"]["criteria"]],
        },
    }
    return yaml.safe_dump(serializable, sort_keys=False, allow_unicode=True)


def preview(config: dict, target: Path) -> dict:
    normalized = validate_config(config)
    core = core_preflight()
    return {
        "schema": "agora-ai-sdlc/install-preview/v1",
        "target": str(target.resolve()),
        "existing_repository": (target / ".git").is_dir(),
        "core": core,
        "project": normalized["project"],
        "profile": normalized["profile"],
        "depth": normalized["depth"],
        "language": normalized["language"],
        "framework": normalized["framework"],
        "pathway": normalized["pathway"],
        "integrations": normalized["integrations"],
        "runtimes": normalized["runtimes"],
        "role_execution": normalized["role_execution"],
        "method": normalized["method"],
        "writes": [
            ".agora project state",
            "ai-sdlc/project.yaml",
            "ai-sdlc/profiles activation record",
            ".agora/skills/agora-ai-sdlc-guided/SKILL.md",
        ],
    }


def _write_project_metadata(target: Path, normalized: dict) -> None:
    directory = target / "ai-sdlc"
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": PROJECT_SCHEMA,
        "project": normalized["project"],
        "language": normalized["language"],
        "framework": normalized["framework"],
        "pathway": normalized["pathway"],
        "integrations": normalized["integrations"],
        "profile": normalized["profile"],
        "depth": normalized["depth"],
        "runtimes": normalized["runtimes"],
        "role_execution": normalized["role_execution"],
        "method": normalized["method"],
    }
    (directory / "project.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _install_guided_skill(target: Path) -> Path:
    source = skill_path()
    if not source.is_file():
        raise InstallerError("installer.skill-missing", f"packaged guided skill not found at {source}")
    destination = target / ".agora" / "skills" / "agora-ai-sdlc-guided" / "SKILL.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return destination


def apply(config: dict, target: Path, home: Path) -> dict:
    normalized = validate_config(config)
    core = core_preflight()
    target.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").is_dir():
        subprocess.run(["git", "init", "-q", str(target)], check=True)

    os.environ["AGORA_HOME"] = str(home.resolve())
    workspace = AgoraWorkspace(cwd=target)
    init_kwargs = {
        "integration": "generic",
        "provider": "local",
        "model": "human",
        "default_method": "scrum",
    }
    fields = getattr(InitInput, "__dataclass_fields__", {})
    if "active_flavor" in fields:
        init_kwargs.update(
            active_flavor="ai-sdlc",
            active_profile=normalized["profile"],
            active_depth=normalized["depth"],
        )
    workspace.initialize(InitInput(**init_kwargs))
    method_source = asset_root("registry") / "method-versions" / METHOD_ID / METHOD_VERSION
    workspace.install_method(
        InstallMethodInput(
            source=str(method_source),
            scope="project",
        )
    )

    actors = [
        AddActorInput(
            "product-owner",
            "Product Owner",
            "human",
            ["specification"],
            "project",
        ),
        AddActorInput(
            "quality-reviewer",
            "Quality Reviewer",
            "human",
            ["review"],
            "project",
        ),
        AddActorInput(
            "delivery-member",
            "Delivery Member",
            "human",
            ["specification", "implementation", "operations"],
            "project",
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
            id=normalized["swarm"],
            objective=normalized["objective"],
            method=METHOD_ID,
            create_branch=False,
        )
    )
    assignments = {
        "product-owner": "product-owner",
        "quality-reviewer": "quality-reviewer",
        "developer": (
            "delivery-member"
            if normalized["role_execution"]["developer"] == "human"
            else f"ai-{normalized['role_execution']['developer']}"
        ),
    }
    for role, actor in assignments.items():
        workspace.assign_actor(
            AssignActorInput(
                swarm_id=normalized["swarm"],
                role_id=role,
                actor_id=actor,
            )
        )

    workspace.create_work(
        CreateWorkInput(
            swarm_id=normalized["swarm"],
            id=normalized["work"]["id"],
            title=normalized["work"]["title"],
            actor_id="product-owner",
            acceptance_criteria=normalized["work"]["criteria"],
        )
    )
    profile_activation.activate(
        workspace,
        normalized["swarm"],
        normalized["work"]["id"],
        "product-owner",
        normalized["profile"],
    )
    _write_project_metadata(target, normalized)
    installed_skill = _install_guided_skill(target)
    validation = workspace.validate()
    work = workspace.show_work(normalized["swarm"], normalized["work"]["id"])
    return {
        **preview(normalized, target),
        "core": core,
        "validate": "ok" if validation.ok else "failed",
        "core_validation": "ok" if validation.ok else "failed",
        "work_state": work.state,
        "swarm": normalized["swarm"],
        "work": normalized["work"]["id"],
        "guided_skill": str(installed_skill.relative_to(target)),
        "next_commands": [
            "agora validate",
            "agora status --board",
            "agora-ai-sdlc continue",
        ],
    }


def _ask(input_fn, prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    answer = input_fn(f"{prompt}{suffix}: ").strip()
    return answer or (default or "")


def _choose(input_fn, prompt: str, choices: tuple[str, ...], default: str) -> str:
    while True:
        answer = _ask(input_fn, f"{prompt} ({'/'.join(choices)})", default)
        if answer in choices:
            return answer


def _yes_no(input_fn, prompt: str, default: bool = False) -> bool:
    marker = "Y/n" if default else "y/N"
    answer = input_fn(f"{prompt} [{marker}]: ").strip().casefold()
    if not answer:
        return default
    return answer in {"y", "yes"}


def wizard(
    target: Path,
    *,
    input_fn=input,
    output_fn=print,
) -> dict:
    existing = (target / ".git").is_dir()
    project_id = _ask(
        input_fn,
        "Project id",
        re.sub(r"[^a-z0-9-]+", "-", target.name.lower()).strip("-") or "project",
    )
    project_name = _ask(input_fn, "Project name", target.name or project_id)
    profile = _choose(input_fn, "Adoption profile", PROFILE_IDS, "starter")
    default_depth = _profile_default_depth(profile)
    allowed_depths = tuple(depth for depth in DEPTH_ORDER if _depth_at_least(depth, default_depth))
    depth = _choose(input_fn, "Governance depth", allowed_depths, default_depth)
    language = _ask(input_fn, "Primary programming language", "java")
    framework = _ask(input_fn, "Framework (optional)", "") or None
    pathway = _choose(
        input_fn,
        "Delivery pathway",
        ("new-product", "brownfield", "refactor", "regulated-change", "scaling", "trivial-change"),
        "brownfield" if existing else "new-product",
    )

    detected = discover_runtimes(target)
    output_fn(render_runtimes(detected))
    output_fn("Select only the runtimes you want to enable; detection does not configure them.")

    integrations = []
    for integration in OPTIONAL_INTEGRATIONS:
        if _yes_no(input_fn, f"Enable {integration} integration?", False):
            integrations.append(integration)

    runtimes = []
    while _yes_no(input_fn, "Add an AI runtime?", not runtimes):
        runtime_id = _ask(input_fn, "Runtime id", "primary" if not runtimes else f"runtime-{len(runtimes) + 1}")
        integration = _choose(input_fn, "Core integration", INTEGRATIONS, "generic")
        provider = _ask(input_fn, "Provider", "local")
        model = _ask(input_fn, "Model", "local")
        runtimes.append(
            {
                "id": runtime_id,
                "integration": integration,
                "provider": provider,
                "model": model,
            }
        )

    runtime_choices = ("human", *(runtime["id"] for runtime in runtimes))
    role_execution = {
        "developer": _choose(input_fn, "Executor for developer", runtime_choices, runtime_choices[-1])
    }
    swarm = _ask(input_fn, "Delivery swarm id", "delivery")
    objective = _ask(input_fn, "Project objective", f"Deliver {project_name}")
    work_id = _ask(input_fn, "First work id", "first-work")
    work_title = _ask(input_fn, "First work title", "Deliver first governed outcome")
    criterion = _ask(
        input_fn,
        "First acceptance criterion",
        "The first outcome is implemented, reviewed and evidenced",
    )

    config = {
        "schema": SCHEMA,
        "project": {
            "id": project_id,
            "name": project_name,
            "mode": "existing" if existing else "new",
        },
        "profile": profile,
        "depth": depth,
        "language": language,
        "framework": framework,
        "pathway": pathway,
        "integrations": integrations,
        "runtimes": runtimes,
        "role_execution": role_execution,
        "swarm": swarm,
        "objective": objective,
        "work": {
            "id": work_id,
            "title": work_title,
            "criteria": [{"id": "outcome", "text": criterion}],
        },
    }
    normalized = validate_config(config)
    output_fn(json.dumps(preview(normalized, target), sort_keys=True))
    return normalized
