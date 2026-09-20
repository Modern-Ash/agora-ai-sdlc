"""Flavor manifest `agora/flavor/v1`: typed, immutable, validated locally without network access."""

import re
from dataclasses import dataclass
from importlib import metadata, resources
from pathlib import Path
from typing import Any

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

SCHEMA = "agora/flavor/v1"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
REQUIRED = ("schema", "id", "name", "version", "supported_core")
LIST_FIELDS = ("method_packs", "profiles", "policies", "required_capabilities")
# Normative fields drive behavior; `metadata` is presentation-only and ignored by validation.
ALLOWED = set(REQUIRED) | set(LIST_FIELDS) | {"metadata"}


class ManifestError(ValueError):
    """Stable, machine-matchable failure: `code` is part of the contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class FlavorManifest:
    id: str
    name: str
    version: str
    supported_core: str
    method_packs: tuple[str, ...]
    profiles: tuple[str, ...]
    policies: tuple[str, ...]
    required_capabilities: tuple[str, ...]


def parse_manifest(contents: str) -> FlavorManifest:
    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as error:
        raise ManifestError("manifest.syntax", "not valid YAML") from error
    if not isinstance(data, dict):
        raise ManifestError("manifest.syntax", "top level must be a mapping")
    schema = data.get("schema")
    if schema != SCHEMA:
        raise ManifestError("manifest.schema", f"unsupported schema {schema!r}; expected {SCHEMA}")
    for key in REQUIRED:
        if key not in data:
            raise ManifestError("manifest.missing", f"missing required field {key!r}")
    unknown = sorted(set(data) - ALLOWED)
    if unknown:
        raise ManifestError("manifest.unknown", f"unknown fields: {', '.join(unknown)}")
    for key in ("id", "name", "version", "supported_core"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ManifestError("manifest.type", f"{key!r} must be a non-empty string")
    if not ID_PATTERN.match(data["id"]):
        raise ManifestError("manifest.id", f"invalid id {data['id']!r}")
    if not SEMVER.match(data["version"]):
        raise ManifestError("manifest.version", f"invalid semantic version {data['version']!r}")
    try:
        SpecifierSet(data["supported_core"])
    except InvalidSpecifier as error:
        raise ManifestError("manifest.core_range", f"invalid Core range {data['supported_core']!r}") from error
    lists: dict[str, tuple[str, ...]] = {}
    for key in LIST_FIELDS:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise ManifestError("manifest.type", f"{key!r} must be a list of non-empty strings")
        if len(set(value)) != len(value):
            raise ManifestError("manifest.duplicate", f"duplicate entries in {key!r}")
        lists[key] = tuple(value)
    if "metadata" in data and not isinstance(data["metadata"], dict):
        raise ManifestError("manifest.type", "'metadata' must be a mapping")
    return FlavorManifest(
        id=data["id"], name=data["name"], version=data["version"],
        supported_core=data["supported_core"], **lists,
    )


def load_manifest(path: Path) -> FlavorManifest:
    return parse_manifest(path.read_text(encoding="utf-8"))


def load_packaged_manifest() -> FlavorManifest:
    text = resources.files("agora_ai_sdlc").joinpath("flavor/flavor.yaml").read_text(encoding="utf-8")
    return parse_manifest(text)


def installed_core_version() -> str:
    return metadata.version("agora-framework")


def check_core_compatibility(manifest: FlavorManifest, installed: str | None = None) -> None:
    installed = installed or installed_core_version()
    try:
        compatible = Version(installed) in SpecifierSet(manifest.supported_core)
    except InvalidVersion as error:
        raise ManifestError("manifest.core_version", f"invalid installed Core version {installed!r}") from error
    if not compatible:
        raise ManifestError(
            "manifest.core_incompatible",
            f"installed Core {installed} is outside supported range {manifest.supported_core}",
        )
