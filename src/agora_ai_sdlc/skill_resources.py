"""Provider-neutral progressive skill loading, without model calls."""

from __future__ import annotations

import hashlib
from pathlib import Path

from agora_ai_sdlc.depth_profiles import asset_root

PHASES = ("inception", "construction", "review", "delivery", "readiness", "governance")
MAX_RESOURCE_BYTES = 32768


def resource_root() -> Path:
    return asset_root("skills") / "agora-ai-sdlc-guided"


def resource_paths(phase: str | None = None) -> tuple[Path, ...]:
    if phase is not None and phase not in PHASES:
        raise ValueError("skill.unknown-phase")
    root = resource_root()
    paths = (root / "SKILL.md",)
    if phase is not None:
        paths += (root / "references" / f"{phase}.md",)
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError("skill.resource-unavailable")
        if path.stat().st_size > MAX_RESOURCE_BYTES:
            raise ValueError("skill.resource-too-large")
    return paths


def bundle(phase: str | None = None, *, include_content: bool = False) -> dict:
    """Same phase contract for every executor; no locale, activity, or UI-detail input."""
    resources = []
    root = resource_root()
    for path in resource_paths(phase):
        content = path.read_bytes()
        if len(content) > MAX_RESOURCE_BYTES:
            raise ValueError("skill.resource-too-large")
        resource = {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
        if include_content:
            resource["content"] = content.decode("utf-8")
        resources.append(resource)
    return {
        "schema": "agora-ai-sdlc/skill-bundle/v1",
        "phase": phase,
        "resources": resources,
        "content_bytes": sum(r["bytes"] for r in resources),
        "token_count": None,
    }


def install_resources(source: Path, destination: Path) -> Path:
    """Copy the entire skill resource set. Preflight before replacing any resource.

    Unrelated/user-created files are left untouched. Symlink destinations are rejected.
    The caller owns the explicit install/update operation; this is not lifecycle state.
    """
    relatives = (Path("SKILL.md"), *(Path("references") / f"{phase}.md" for phase in PHASES))
    content = {}
    for relative in relatives:
        src = source / relative
        dst = destination / relative
        if not src.is_file() or src.is_symlink() or src.stat().st_size > MAX_RESOURCE_BYTES:
            raise ValueError("skill.resource-unavailable")
        for path in (dst, *dst.parents):
            if path.is_symlink():
                raise ValueError("skill.install-symlink")
        if dst.exists() and not dst.is_file():
            raise ValueError("skill.install-not-file")
        content[relative] = src.read_text(encoding="utf-8")
    for relative, text in content.items():
        dst = destination / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file() or dst.read_text(encoding="utf-8") != text:
            dst.write_text(text, encoding="utf-8")
    return destination / "SKILL.md"
