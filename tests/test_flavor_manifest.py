import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from agora_ai_sdlc.flavor_manifest import (
    ManifestError, check_core_compatibility, load_manifest, load_packaged_manifest, parse_manifest,
)

GOLDEN = Path(__file__).parent / "fixtures" / "flavor-valid.yaml"


def valid(**overrides):
    lines = {
        "schema": "agora/flavor/v1", "id": "x", "name": "X", "version": "1.0.0",
        "supported_core": '">=0.8,<0.9"',
    }
    lines.update(overrides)
    return "\n".join(f"{k}: {v}" for k, v in lines.items() if v is not None) + "\n"


def code(text):
    with pytest.raises(ManifestError) as exc:
        parse_manifest(text)
    return exc.value.code


def test_golden_manifest_is_typed_and_immutable():
    manifest = load_manifest(GOLDEN)
    assert manifest.id == "golden" and manifest.method_packs == ("ai-sdlc", "other")
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.id = "changed"  # type: ignore[misc]


def test_packaged_manifest_loads():
    assert load_packaged_manifest().id == "agora-ai-sdlc"


@pytest.mark.parametrize("field", ["schema", "id", "name", "version", "supported_core"])
def test_missing_required_field(field):
    expected = "manifest.schema" if field == "schema" else "manifest.missing"
    assert code(valid(**{field: None})) == expected


def test_forward_incompatible_schema():
    assert code(valid(schema="agora/flavor/v2")) == "manifest.schema"


def test_unknown_field_rejected():
    assert code(valid(extra="1")) == "manifest.unknown"


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "01.0.0", "abc"])
def test_invalid_semver(version):
    assert code(valid(version=f'"{version}"')) == "manifest.version"


def test_invalid_id_and_core_range():
    assert code(valid(id="Bad_Id")) == "manifest.id"
    assert code(valid(supported_core='"not a range"')) == "manifest.core_range"


def test_duplicate_and_bad_list_entries():
    assert code(valid(method_packs="[a, a]")) == "manifest.duplicate"
    assert code(valid(profiles="[1]")) == "manifest.type"
    assert code(valid(policies="text")) == "manifest.type"


def test_syntax_errors():
    assert code("a: [") == "manifest.syntax"
    assert code("- just\n- a list\n") == "manifest.syntax"


def test_compatibility_failure_names_versions():
    manifest = parse_manifest(valid())
    check_core_compatibility(manifest, "0.8.5")
    with pytest.raises(ManifestError) as exc:
        check_core_compatibility(manifest, "0.9.0")
    assert exc.value.code == "manifest.core_incompatible"
    assert "0.9.0" in str(exc.value) and ">=0.8,<0.9" in str(exc.value)


def test_no_network_imports():
    out = subprocess.run(
        [sys.executable, "-c", "import sys, agora_ai_sdlc.flavor_manifest as m; print(any(n.split('.')[0] in ('requests','urllib3','httpx') for n in sys.modules))"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out == "False"
