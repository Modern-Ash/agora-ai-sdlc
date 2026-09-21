"""Versioned AI-SDLC Method Pack selection."""

from pathlib import Path

from agora_ai_sdlc.depth_profiles import asset_root

DEFAULT_METHOD_VERSION = "0.1.0"
DEFAULT_CANDIDATE_VERSION = "0.2.0"
SUPPORTED_METHOD_VERSIONS = (DEFAULT_METHOD_VERSION, DEFAULT_CANDIDATE_VERSION)


class MethodVersionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def method_pack_path(version: str = DEFAULT_METHOD_VERSION) -> Path:
    if version == "0.1.0":
        path = asset_root("registry") / "methods" / "ai-sdlc"
    elif version == "0.2.0":
        path = asset_root("registry") / "method-versions" / "ai-sdlc" / version
    else:
        raise MethodVersionError("method.version_unknown", f"unsupported AI-SDLC Method Pack version {version!r}")
    if not (path / "METHOD.md").is_file():
        raise MethodVersionError("method.version_missing", f"packaged Method Pack {version!r} is missing")
    return path
