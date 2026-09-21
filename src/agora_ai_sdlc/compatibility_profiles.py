"""Versioned compatibility profiles for public AI-SDLC method presentations.

The contracts under profiles/compatibility describe how a small, provider-neutral
Agora canonical element vocabulary is presented by an external public method or
enterprise operating model. They are compatibility targets, not claims of
affiliation, endorsement, certification, or implementation of non-public behavior.
"""

import re
from dataclasses import dataclass

import yaml

from agora_ai_sdlc.depth_profiles import asset_root

SCHEMA = "agora-ai-sdlc/compatibility-profile/v1"
CANONICAL_MODEL = "agora-ai-sdlc/canonical-elements/v1"
CANONICAL_ELEMENTS = frozenset({"readiness", "intent", "inception", "construction", "operations"})
NEUTRALITY_DIMENSIONS = ("provider", "model", "cloud", "scm", "agent-runtime")
CAPABILITY_GROUPS = ("required", "optional", "unsupported")

ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

TOP_REQUIRED = ("schema", "id", "name", "version", "canonical_model", "source", "stages", "capabilities", "neutrality")
TOP_ALLOWED = set(TOP_REQUIRED) | {"metadata"}
SOURCE_REQUIRED = ("basis", "references", "affiliation", "runtime_dependency")
STAGE_REQUIRED = ("id", "label", "maps_from")


class CompatibilityProfileError(ValueError):
    """Stable, machine-matchable compatibility-profile validation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class SourceDeclaration:
    references: tuple[str, ...]


@dataclass(frozen=True)
class StageMapping:
    id: str
    label: str
    maps_from: tuple[str, ...]


@dataclass(frozen=True)
class CompatibilityProfile:
    id: str
    name: str
    version: str
    canonical_model: str
    source: SourceDeclaration
    stages: tuple[StageMapping, ...]
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...]
    unsupported_capabilities: tuple[str, ...]
    neutrality: tuple[str, ...]

    def stage(self, stage_id: str) -> StageMapping:
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        raise CompatibilityProfileError("compatibility.stage_unknown", f"unknown presentation stage {stage_id!r}")


def _non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompatibilityProfileError("compatibility.type", f"{field!r} must be a non-empty string")
    return value


def _id(value: object, field: str) -> str:
    text = _non_empty_string(value, field)
    if not ID_PATTERN.fullmatch(text):
        raise CompatibilityProfileError("compatibility.id", f"invalid {field} {text!r}")
    return text


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise CompatibilityProfileError("compatibility.type", f"{field!r} must be a list of non-empty strings")
    if len(set(value)) != len(value):
        raise CompatibilityProfileError("compatibility.duplicate", f"duplicate entries in {field!r}")
    return tuple(value)


def parse_profile(contents: str) -> CompatibilityProfile:
    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as error:
        raise CompatibilityProfileError("compatibility.syntax", "not valid YAML") from error
    if not isinstance(data, dict):
        raise CompatibilityProfileError("compatibility.syntax", "top level must be a mapping")

    if data.get("schema") != SCHEMA:
        raise CompatibilityProfileError(
            "compatibility.schema", f"unsupported schema {data.get('schema')!r}; expected {SCHEMA}"
        )
    for field in TOP_REQUIRED:
        if field not in data:
            raise CompatibilityProfileError("compatibility.missing", f"missing required field {field!r}")
    unknown = sorted(set(data) - TOP_ALLOWED)
    if unknown:
        raise CompatibilityProfileError("compatibility.unknown", f"unknown fields: {', '.join(unknown)}")

    profile_id = _id(data["id"], "id")
    name = _non_empty_string(data["name"], "name")
    version = _non_empty_string(data["version"], "version")
    if not SEMVER.fullmatch(version):
        raise CompatibilityProfileError("compatibility.version", f"invalid semantic version {version!r}")
    if data["canonical_model"] != CANONICAL_MODEL:
        raise CompatibilityProfileError(
            "compatibility.canonical_model",
            f"unsupported canonical model {data['canonical_model']!r}; expected {CANONICAL_MODEL}",
        )

    source = data["source"]
    if not isinstance(source, dict):
        raise CompatibilityProfileError("compatibility.type", "'source' must be a mapping")
    missing_source = [field for field in SOURCE_REQUIRED if field not in source]
    if missing_source:
        raise CompatibilityProfileError("compatibility.missing", f"missing source fields: {', '.join(missing_source)}")
    unknown_source = sorted(set(source) - set(SOURCE_REQUIRED))
    if unknown_source:
        raise CompatibilityProfileError("compatibility.unknown", f"unknown source fields: {', '.join(unknown_source)}")
    if source["basis"] != "public":
        raise CompatibilityProfileError("compatibility.source_scope", "compatibility sources must be public")
    references = _string_list(source["references"], "source.references")
    if not references or not all(reference.startswith("https://") for reference in references):
        raise CompatibilityProfileError(
            "compatibility.source_scope", "source.references must contain public HTTPS references"
        )
    if source["affiliation"] is not False:
        raise CompatibilityProfileError(
            "compatibility.affiliation", "compatibility profile must explicitly declare affiliation: false"
        )
    if source["runtime_dependency"] is not False:
        raise CompatibilityProfileError(
            "compatibility.dependency", "compatibility profile must explicitly declare runtime_dependency: false"
        )

    raw_stages = data["stages"]
    if not isinstance(raw_stages, list) or not raw_stages:
        raise CompatibilityProfileError("compatibility.type", "'stages' must be a non-empty list")
    stages: list[StageMapping] = []
    stage_ids: set[str] = set()
    mapped: dict[str, str] = {}
    for index, raw_stage in enumerate(raw_stages):
        if not isinstance(raw_stage, dict):
            raise CompatibilityProfileError("compatibility.type", f"stages[{index}] must be a mapping")
        missing = [field for field in STAGE_REQUIRED if field not in raw_stage]
        if missing:
            raise CompatibilityProfileError(
                "compatibility.missing", f"stages[{index}] missing fields: {', '.join(missing)}"
            )
        unknown_stage = sorted(set(raw_stage) - set(STAGE_REQUIRED))
        if unknown_stage:
            raise CompatibilityProfileError(
                "compatibility.unknown", f"stages[{index}] unknown fields: {', '.join(unknown_stage)}"
            )
        stage_id = _id(raw_stage["id"], f"stages[{index}].id")
        if stage_id in stage_ids:
            raise CompatibilityProfileError("compatibility.stage_duplicate", f"duplicate stage id {stage_id!r}")
        stage_ids.add(stage_id)
        label = _non_empty_string(raw_stage["label"], f"stages[{index}].label")
        maps_from = _string_list(raw_stage["maps_from"], f"stages[{index}].maps_from")
        if not maps_from:
            raise CompatibilityProfileError(
                "compatibility.mapping_empty", f"stage {stage_id!r} must map at least one canonical element"
            )
        for canonical in maps_from:
            if canonical not in CANONICAL_ELEMENTS:
                raise CompatibilityProfileError(
                    "compatibility.mapping_unknown",
                    f"stage {stage_id!r} maps unknown canonical element {canonical!r}",
                )
            if canonical in mapped:
                raise CompatibilityProfileError(
                    "compatibility.mapping_duplicate",
                    f"canonical element {canonical!r} is mapped by both {mapped[canonical]!r} and {stage_id!r}",
                )
            mapped[canonical] = stage_id
        stages.append(StageMapping(stage_id, label, maps_from))

    capabilities = data["capabilities"]
    if not isinstance(capabilities, dict):
        raise CompatibilityProfileError("compatibility.type", "'capabilities' must be a mapping")
    if set(capabilities) != set(CAPABILITY_GROUPS):
        missing = sorted(set(CAPABILITY_GROUPS) - set(capabilities))
        unknown_groups = sorted(set(capabilities) - set(CAPABILITY_GROUPS))
        detail = []
        if missing:
            detail.append(f"missing={missing}")
        if unknown_groups:
            detail.append(f"unknown={unknown_groups}")
        raise CompatibilityProfileError(
            "compatibility.capability_groups",
            "capability groups must be required/optional/unsupported; " + ", ".join(detail),
        )

    capability_sets: dict[str, tuple[str, ...]] = {}
    owners: dict[str, str] = {}
    for group in CAPABILITY_GROUPS:
        values = _string_list(capabilities[group], f"capabilities.{group}")
        for capability in values:
            if not ID_PATTERN.fullmatch(capability):
                raise CompatibilityProfileError(
                    "compatibility.capability_id", f"invalid capability id {capability!r} in {group}"
                )
            if capability in owners:
                raise CompatibilityProfileError(
                    "compatibility.capability_overlap",
                    f"capability {capability!r} appears in both {owners[capability]!r} and {group!r}",
                )
            owners[capability] = group
        capability_sets[group] = values

    neutrality = data["neutrality"]
    if not isinstance(neutrality, dict):
        raise CompatibilityProfileError("compatibility.type", "'neutrality' must be a mapping")
    if set(neutrality) != set(NEUTRALITY_DIMENSIONS):
        raise CompatibilityProfileError(
            "compatibility.neutrality",
            f"neutrality must declare exactly: {', '.join(NEUTRALITY_DIMENSIONS)}",
        )
    disabled = [dimension for dimension in NEUTRALITY_DIMENSIONS if neutrality[dimension] is not True]
    if disabled:
        raise CompatibilityProfileError(
            "compatibility.neutrality", f"neutrality dimensions must be true: {', '.join(disabled)}"
        )

    if "metadata" in data and not isinstance(data["metadata"], dict):
        raise CompatibilityProfileError("compatibility.type", "'metadata' must be a mapping")

    return CompatibilityProfile(
        id=profile_id,
        name=name,
        version=version,
        canonical_model=CANONICAL_MODEL,
        source=SourceDeclaration(references),
        stages=tuple(stages),
        required_capabilities=capability_sets["required"],
        optional_capabilities=capability_sets["optional"],
        unsupported_capabilities=capability_sets["unsupported"],
        neutrality=NEUTRALITY_DIMENSIONS,
    )


def load_profile(profile_id: str) -> CompatibilityProfile:
    profile_id = _id(profile_id, "profile_id")
    path = asset_root("profiles") / "compatibility" / profile_id / "profile.yaml"
    if not path.is_file():
        raise CompatibilityProfileError(
            "compatibility.profile_unknown", f"unknown compatibility profile {profile_id!r}"
        )
    profile = parse_profile(path.read_text(encoding="utf-8"))
    if profile.id != profile_id:
        raise CompatibilityProfileError(
            "compatibility.profile_mismatch", f"{path} declares id {profile.id!r}, expected {profile_id!r}"
        )
    return profile


def available_profiles() -> tuple[str, ...]:
    root = asset_root("profiles") / "compatibility"
    if not root.is_dir():
        return ()
    return tuple(
        path.parent.name
        for path in sorted(root.glob("*/profile.yaml"))
        if path.parent.name and ID_PATTERN.fullmatch(path.parent.name)
    )
