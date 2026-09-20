"""Credential-free conformance harness over packaged AI-SDLC assets."""

import io
import json
import os
import runpy
import shutil
import tempfile
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import mkdtemp

import yaml
from agora.markdown import read_markdown, strings_attribute
from agora.model import AddActorInput, AddArtifactInput, AssignActorInput, CreateSwarmInput, CreateWorkInput

from agora_ai_sdlc import (
    ci_evidence,
    enterprise,
    github_delivery,
    modernization,
    operational_evidence,
    security_findings,
    starter,
)
from agora_ai_sdlc.depth_profiles import ORDER, asset_root, resolve
from agora_ai_sdlc.flavor_manifest import check_core_compatibility, load_packaged_manifest
from agora_ai_sdlc.follow_on_delivery import load_profile as load_follow_on_profile
from agora_ai_sdlc.scenario import SWARM, Lifecycle

RESULT_SCHEMA = "agora-ai-sdlc/self-test-result/v1"
PROFILE_SCHEMAS = {
    "agora-ai-sdlc/depth-profile/v1",
    "agora-ai-sdlc/integration-profile/v1",
    "agora-ai-sdlc/adoption-profile/v1",
}


def _yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path.name} must contain a YAML mapping")
    return data


def _discover_assets() -> dict[str, list[str]]:
    profiles_root = asset_root("profiles")
    profile_files = sorted(profiles_root.rglob("*.yaml"))
    profile_ids: list[str] = []
    profile_names: list[str] = []
    for path in profile_files:
        data = _yaml(path)
        if data.get("schema") not in PROFILE_SCHEMAS or not isinstance(data.get("id"), str):
            raise ValueError(f"invalid profile contract: {path.relative_to(profiles_root)}")
        profile_ids.append(data["id"])
        relative = path.relative_to(profiles_root)
        profile_names.append(
            relative.parent.as_posix() if relative.name == "profile.yaml" else relative.with_suffix("").as_posix()
        )
    if len(profile_names) != len(set(profile_names)):
        raise ValueError("profile paths must be unique")

    for depth in ORDER:
        resolve(depth)
    for loader in (
        ci_evidence.load_profile,
        enterprise.load_profile,
        github_delivery.load_profile,
        modernization.load_profile,
        operational_evidence.load_profile,
        security_findings.load_profile,
        starter.load_profile,
    ):
        loader()
    load_follow_on_profile("gitlab")
    load_follow_on_profile("jira")

    policies_root = asset_root("policies")
    policy_files = sorted(policies_root.rglob("*.yaml"))
    for path in policy_files:
        data = _yaml(path)
        if not isinstance(data.get("schema"), str):
            raise TypeError(f"invalid policy contract: {path.relative_to(policies_root)}")
    policy_ids = sorted({path.parent.name for path in policy_files})

    templates_root = asset_root("templates")
    templates = sorted(path.stem for path in templates_root.glob("*.md") if path.name != "README.md")
    for name in templates:
        if not (templates_root / f"{name}.md").read_text(encoding="utf-8").strip():
            raise ValueError(f"empty template: {name}")

    contracts_root = asset_root("contracts")
    contracts = []
    for path in sorted(contracts_root.rglob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))
        contracts.append(path.relative_to(contracts_root).as_posix())

    samples_root = asset_root("samples")
    samples = sorted(path.parent.name for path in samples_root.glob("*/run.py"))
    if not samples:
        raise ValueError("no executable samples were discovered")

    manifest = load_packaged_manifest()
    check_core_compatibility(manifest)
    missing_profiles = sorted(set(manifest.profiles) - set(profile_ids))
    missing_policies = sorted(set(manifest.policies) - set(policy_ids))
    if missing_profiles or missing_policies:
        raise ValueError(f"manifest references missing profiles={missing_profiles}, policies={missing_policies}")
    method_root = asset_root("registry") / "methods"
    methods = sorted(path.name for path in method_root.iterdir() if path.is_dir())
    if sorted(manifest.method_packs) != methods:
        raise ValueError("manifest Method Pack inventory differs from packaged methods")
    return {
        "methods": methods,
        "profiles": sorted(profile_names),
        "policies": policy_ids,
        "templates": templates,
        "contracts": contracts,
        "samples": samples,
    }


def _role_capabilities(method_root: Path, roles: tuple[str, ...]) -> list[str]:
    capabilities: set[str] = set()
    for role in roles:
        attributes = read_markdown(method_root / "roles" / f"{role}.md").attributes
        capabilities.update(strings_attribute(attributes, "required-capabilities"))
    return sorted(capabilities)


def _role_conformance(root: Path) -> dict:
    lifecycle = Lifecycle(root / "role-conformance", root / "home")
    parent = lifecycle.ws.show_swarm(SWARM)
    method_root = lifecycle.root / ".agora" / "methods" / "ai-sdlc"
    capabilities = _role_capabilities(method_root, parent.required_roles)
    lifecycle.ws.add_actor(AddActorInput("service", "Service", "service", capabilities, "project"))
    lifecycle.ws.add_actor(AddActorInput("role-holder", "Role holder", "human", capabilities, "project"))
    probe = lifecycle.ws.create_swarm(
        CreateSwarmInput("role-probe", "Exercise actor-kind role conformance", "ai-sdlc", False)
    )
    service_rejections = 0
    for role in probe.required_roles:
        try:
            lifecycle.ws.assign_actor(AssignActorInput(probe.id, role, "service"))
        except ValueError as error:
            if "Actor kind service is not allowed for role" not in str(error):
                raise
            service_rejections += 1
        else:
            raise AssertionError(f"service actor unexpectedly held {role}")

    lifecycle.ws.add_actor(AddActorInput("child-owner", "Child owner", "human", capabilities, "project"))
    child = lifecycle.ws.create_swarm(
        CreateSwarmInput("delegated-team", "Exercise represented-swarm delegation", "ai-sdlc", False)
    )
    for role in child.required_roles:
        lifecycle.ws.assign_actor(AssignActorInput(child.id, role, "child-owner"))
    lifecycle.ws.add_actor(
        AddActorInput(
            "delegated",
            "Delegated swarm",
            "swarm",
            capabilities,
            "project",
            represented_swarm=child.id,
        )
    )
    delegated_roles = []
    for role in probe.required_roles:
        attributes = read_markdown(method_root / "roles" / f"{role}.md").attributes
        if "swarm" in strings_attribute(attributes, "allowed-actor-kinds"):
            actor = "delegated"
            delegated_roles.append(role)
        else:
            actor = "role-holder"
        lifecycle.ws.assign_actor(AssignActorInput(probe.id, role, actor))
    probe_work = lifecycle.ws.create_work(
        CreateWorkInput(probe.id, "actor-kinds", "Exercise delegated holders", "role-holder", [("done", "done")])
    )
    for role in delegated_roles:
        path = lifecycle.root / f"delegated-{role}.md"
        path.write_text(f"# Delegated {role}\n", encoding="utf-8")
        lifecycle.ws.add_artifact(
            AddArtifactInput(probe.id, probe_work.id, "delegated", f"delegated-{role}", f"repo://{path.name}")
        )

    lifecycle.to_intent()
    lifecycle.to_inception()
    lifecycle.to_construction()
    lifecycle.to_operations()
    lifecycle.to_completed()
    validation = lifecycle.ws.validate()
    if not validation.ok:
        raise ValueError("AI-SDLC role conformance workspace is invalid")
    return {
        "actor_kinds": ["human", "ai-agent", "swarm", "service"],
        "human_roles": [
            role for role, actor in lifecycle.ws.show_swarm(SWARM).assignments.items() if "po" in actor or "qa" in actor
        ],
        "ai_roles": [
            role
            for role, actor in lifecycle.ws.show_swarm(SWARM).assignments.items()
            if actor not in {"project:po", "project:qa"}
        ],
        "delegated_roles": delegated_roles,
        "service_assignments_rejected": service_rejections,
        "final_state": lifecycle.state(),
    }


def _run_sample(name: str, root: Path) -> dict:
    script = asset_root("samples") / name / "run.py"
    output = io.StringIO()
    previous_home = os.environ.get("AGORA_HOME")
    previous_tempdir = tempfile.tempdir
    sample_root = root / "samples"
    sample_root.mkdir(exist_ok=True)
    tempfile.tempdir = str(sample_root)
    try:
        with redirect_stdout(output):
            summary = runpy.run_path(str(script), run_name=f"agora_self_test_{name.replace('-', '_')}")["main"]()
    finally:
        tempfile.tempdir = previous_tempdir
        if previous_home is None:
            os.environ.pop("AGORA_HOME", None)
        else:
            os.environ["AGORA_HOME"] = previous_home
    if summary.get("final_state") != "completed" or summary.get("validate") != "ok":
        raise ValueError(f"sample {name} did not complete and validate")
    return {"name": name, "final_state": summary["final_state"], "validate": summary["validate"]}


def run_self_test(
    *,
    progress: Callable[[str], None] | None = None,
    _fail_check: str | None = None,
) -> dict:
    """Run packaged conformance checks; `_fail_check` exists only for deterministic failure tests."""
    root = Path(mkdtemp(prefix="agora-ai-sdlc-self-test-"))
    previous_home = os.environ.get("AGORA_HOME")
    checks: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    assets: dict[str, list[str]] = {
        "methods": [], "profiles": [], "policies": [], "templates": [], "contracts": [], "samples": []
    }  # fmt: skip
    roles: dict = {}

    def execute(check_id: str, kind: str, operation: Callable[[], object]) -> object | None:
        if progress:
            progress(f"{check_id} ...")
        try:
            if _fail_check == check_id:
                raise RuntimeError(f"injected failure at {check_id}")
            value = operation()
        except KeyboardInterrupt:
            raise
        except Exception as error:  # noqa: BLE001 - the harness reports every asset failure uniformly
            checks.append({"id": check_id, "kind": kind, "status": "failed"})
            failures.append({"check": check_id, "type": type(error).__name__, "message": str(error)})
            if progress:
                progress(f"{check_id} failed")
            return None
        checks.append({"id": check_id, "kind": kind, "status": "passed"})
        if progress:
            progress(f"{check_id} passed")
        return value

    try:
        try:
            discovered = execute("assets", "inventory", _discover_assets)
            if isinstance(discovered, dict):
                assets = discovered
            role_result = execute("roles", "core-lifecycle", lambda: _role_conformance(root))
            if isinstance(role_result, dict):
                roles = role_result
            for sample in assets["samples"]:
                execute(f"sample:{sample}", "sample", lambda name=sample: _run_sample(name, root))
        except KeyboardInterrupt:
            shutil.rmtree(root, ignore_errors=True)
            raise

        ok = not failures
        workspace = None if ok else str(root)
        if ok:
            shutil.rmtree(root)
        return {
            "schema": RESULT_SCHEMA,
            "ok": ok,
            "assets": assets,
            "role_conformance": roles,
            "checks": checks,
            "failures": failures,
            "workspace": workspace,
        }
    finally:
        if previous_home is None:
            os.environ.pop("AGORA_HOME", None)
        else:
            os.environ["AGORA_HOME"] = previous_home
